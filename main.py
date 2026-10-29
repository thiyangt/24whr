import io
import re
import time
from pathlib import Path

import pandas as pd
import pdfplumber
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://meteo.gov.lk"
PDF_URL = f"{BASE_URL}/pdfs/twentyfour_pdf.pdf"

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
DAILY_DIR = DATA_DIR / "daily"

RETENTION_DAYS = 90

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ============================================================
# DOWNLOAD WEATHER REPORT
# ============================================================

def download_report():
    """
    Download the latest 24-hour weather report PDF.

    Uses retries and falls back to the official
    Department of Meteorology website if the direct
    PDF URL cannot be reached.
    """

    session = requests.Session()

    session.headers.update(HEADERS)

    # --------------------------------------------------------
    # Attempt 1: Direct PDF URL
    # --------------------------------------------------------

    for attempt in range(1, 4):

        print(
            f"Attempt {attempt}/3: "
            f"Downloading report from {PDF_URL}"
        )

        try:

            response = session.get(
                PDF_URL,
                timeout=(15, 60)
            )

            response.raise_for_status()

            # Make sure we received something substantial
            if len(response.content) < 1000:

                raise RuntimeError(
                    "Downloaded response is too small to be a PDF."
                )

            print(
                "Successfully downloaded the "
                "24-hour weather report."
            )

            return response.content

        except requests.exceptions.RequestException as error:

            print(
                f"Direct PDF attempt {attempt} failed: "
                f"{error}"
            )

            if attempt < 3:

                wait_seconds = attempt * 10

                print(
                    f"Waiting {wait_seconds} seconds "
                    "before retrying..."
                )

                time.sleep(wait_seconds)

    # --------------------------------------------------------
    # Attempt 2: Open official website
    # --------------------------------------------------------

    print(
        "Direct PDF download failed."
    )

    print(
        "Trying the official Department of "
        "Meteorology website..."
    )

    try:

        response = session.get(
            BASE_URL,
            timeout=(15, 60)
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        report_url = None

        # Search all links for 24 Hour Weather Report
        for link in soup.find_all(
            "a",
            href=True
        ):

            link_text = link.get_text(
                " ",
                strip=True
            ).lower()

            href = link["href"]

            if (
                "24 hour weather report"
                in link_text
            ):

                report_url = href

                break

        # ----------------------------------------------------
        # Also search for the known PDF filename
        # ----------------------------------------------------

        if report_url is None:

            for link in soup.find_all(
                "a",
                href=True
            ):

                href = link["href"]

                if (
                    "twentyfour_pdf.pdf"
                    in href.lower()
                ):

                    report_url = href

                    break

        if report_url is None:

            raise RuntimeError(
                "Could not find the 24-hour weather "
                "report link on the official website."
            )

        # Convert relative URL to absolute URL
        report_url = requests.compat.urljoin(
            BASE_URL,
            report_url
        )

        print(
            f"Found report URL: {report_url}"
        )

        # ----------------------------------------------------
        # Download report found through website
        # ----------------------------------------------------

        response = session.get(
            report_url,
            timeout=(15, 60)
        )

        response.raise_for_status()

        if len(response.content) < 1000:

            raise RuntimeError(
                "Fallback report download is too small."
            )

        print(
            "Successfully downloaded the report "
            "using the official website."
        )

        return response.content

    except Exception as error:

        raise RuntimeError(
            "Unable to download the official "
            "24-hour weather report after all "
            "attempts."
        ) from error

    # Check that the response is actually a PDF
    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    if "pdf" not in content_type:
        print(
            f"Warning: unexpected Content-Type: {content_type}"
        )

    return response.content


# ============================================================
# EXTRACT REPORT DATE
# ============================================================

def extract_report_date(pdf_bytes):
    """
    Extract the report date from the PDF text.

    The report uses a date such as:
    2026.10.28
    """

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:

        full_text = ""

        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Look for YYYY.MM.DD
    match = re.search(
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
        full_text
    )

    if not match:
        raise ValueError(
            "Could not find the report date inside the PDF."
        )

    year, month, day = match.groups()

    report_date = (
        f"{int(year):04d}-"
        f"{int(month):02d}-"
        f"{int(day):02d}"
    )

    return report_date


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_cell(value):
    """
    Clean a PDF table cell.
    """

    if value is None:
        return ""

    return (
        str(value)
        .replace("\n", " ")
        .strip()
    )


def to_number(value):
    """
    Convert a PDF cell to a number.

    'Trace' rainfall is represented as 0.001.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() == "trace":
        return 0.001

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        value
    )

    if match:
        return float(match.group())

    return None


def extract_english_station_name(value):
    """
    Extract the English station name from the
    multilingual station cell.
    """

    value = clean_cell(value)

    # English station name normally appears at the
    # end of the multilingual station cell.
    matches = re.findall(
        r"[A-Za-z][A-Za-z\s().'\-/]*$",
        value
    )

    if matches:

        name = matches[-1].strip()

        # Avoid returning very short fragments
        if len(name) >= 2:
            return name

    return value


# ============================================================
# PARSE WEATHER TABLE
# ============================================================

def parse_weather_report(pdf_bytes, report_date):
    """
    Extract weather observations from the PDF.

    The report contains:

    1. Meteorological Stations
       - Maximum temperature
       - Minimum temperature
       - Daily rainfall

    2. Rainfall Stations
       - Daily rainfall

    3. Other Rainfall Stations
       - Daily rainfall

    All observations are converted into one tidy dataset.
    """

    records = []

    with pdfplumber.open(
        io.BytesIO(pdf_bytes)
    ) as pdf:

        for page in pdf.pages:

            tables = page.extract_tables()

            for table in tables:

                if not table:
                    continue

                for row in table:

                    cleaned = [
                        clean_cell(cell)
                        for cell in row
                    ]

                    if not any(cleaned):
                        continue

                    row_text = " ".join(
                        cleaned
                    ).lower()

                    # Ignore headers and report labels
                    skip_phrases = [
                        "meteorological stations",
                        "rainfall stations",
                        "hydro catchment areas",
                        "other rainfall stations",
                        "temperature in the shade",
                        "daily rainfall",
                        "highest rainfall",
                        "weather report",
                        "for the 24 hour period",
                    ]

                    if any(
                        phrase in row_text
                        for phrase in skip_phrases
                    ):
                        continue

                    # ------------------------------------------------
                    # Find numeric cells
                    # ------------------------------------------------

                    numeric_values = []

                    for cell in cleaned:

                        number = to_number(cell)

                        if number is not None:
                            numeric_values.append(number)

                    # ------------------------------------------------
                    # Main meteorological station rows
                    #
                    # Station | Max | Min | Rainfall
                    # ------------------------------------------------

                    if len(numeric_values) >= 3:

                        max_temp = numeric_values[-3]
                        min_temp = numeric_values[-2]
                        rainfall = numeric_values[-1]

                        # Find first non-numeric cell
                        station_cell = None

                        for cell in cleaned:

                            if (
                                cell
                                and to_number(cell)
                                is None
                            ):
                                station_cell = cell
                                break

                        if station_cell:

                            station = (
                                extract_english_station_name(
                                    station_cell
                                )
                            )

                            if station:

                                records.append(
                                    {
                                        "observation_date":
                                            report_date,
                                        "station":
                                            station,
                                        "max_temperature_c":
                                            max_temp,
                                        "min_temperature_c":
                                            min_temp,
                                        "rainfall_mm":
                                            rainfall,
                                        "station_type":
                                            "Meteorological Station",
                                    }
                                )

                        continue

                    # ------------------------------------------------
                    # Rainfall station rows
                    #
                    # Some tables contain:
                    #
                    # Station A | Rainfall A |
                    # Station B | Rainfall B
                    # ------------------------------------------------

                    if len(numeric_values) == 2:

                        text_cells = [
                            cell
                            for cell in cleaned
                            if cell
                            and to_number(cell)
                            is None
                        ]

                        if len(text_cells) >= 2:

                            station_1 = (
                                extract_english_station_name(
                                    text_cells[0]
                                )
                            )

                            station_2 = (
                                extract_english_station_name(
                                    text_cells[1]
                                )
                            )

                            records.append(
                                {
                                    "observation_date":
                                        report_date,
                                    "station":
                                        station_1,
                                    "max_temperature_c":
                                        None,
                                    "min_temperature_c":
                                        None,
                                    "rainfall_mm":
                                        numeric_values[0],
                                    "station_type":
                                        "Rainfall Station",
                                }
                            )

                            records.append(
                                {
                                    "observation_date":
                                        report_date,
                                    "station":
                                        station_2,
                                    "max_temperature_c":
                                        None,
                                    "min_temperature_c":
                                        None,
                                    "rainfall_mm":
                                        numeric_values[1],
                                    "station_type":
                                        "Rainfall Station",
                                }
                            )

    df = pd.DataFrame(records)

    if df.empty:

        raise RuntimeError(
            "No weather observations were extracted "
            "from the PDF."
        )

    # Remove duplicate station/date combinations
    df = df.drop_duplicates(
        subset=[
            "observation_date",
            "station"
        ],
        keep="first"
    )

    # Sort dataset
    df = df.sort_values(
        [
            "observation_date",
            "station"
        ]
    )

    return df


# ============================================================
# SAVE DATA
# ============================================================

def save_data(pdf_bytes, df, report_date):
    """
    Save:
    1. Raw PDF
    2. Daily tidy CSV
    3. Master tidy CSV
    """

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    DAILY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Save raw PDF
    # --------------------------------------------------------

    pdf_path = (
        RAW_DIR /
        f"weather_report_{report_date}.pdf"
    )

    pdf_path.write_bytes(
        pdf_bytes
    )

    print(
        f"Saved PDF: {pdf_path}"
    )

    # --------------------------------------------------------
    # Save daily CSV
    # --------------------------------------------------------

    daily_csv = (
        DAILY_DIR /
        f"weather_report_{report_date}.csv"
    )

    df.to_csv(
        daily_csv,
        index=False
    )

    print(
        f"Saved daily dataset: {daily_csv}"
    )

    # --------------------------------------------------------
    # Update master tidy dataset
    # --------------------------------------------------------

    master_csv = (
        DATA_DIR /
        "weather_tidy.csv"
    )

    if master_csv.exists():

        existing = pd.read_csv(
            master_csv
        )

        combined = pd.concat(
            [
                existing,
                df
            ],
            ignore_index=True
        )

    else:

        combined = df

    combined = combined.drop_duplicates(
        subset=[
            "observation_date",
            "station"
        ],
        keep="last"
    )

    combined = combined.sort_values(
        [
            "observation_date",
            "station"
        ]
    )

    combined.to_csv(
        master_csv,
        index=False
    )

    print(
        f"Updated master dataset: {master_csv}"
    )


# ============================================================
# REMOVE FILES OLDER THAN 90 DAYS
# ============================================================

def cleanup_old_files():
    """
    Remove daily CSV and PDF files older than 90 days.
    """

    cutoff_time = (
        time.time()
        - RETENTION_DAYS * 24 * 60 * 60
    )

    for directory in [
        RAW_DIR,
        DAILY_DIR
    ]:

        if not directory.exists():
            continue

        for file_path in directory.iterdir():

            if not file_path.is_file():
                continue

            if file_path.stat().st_mtime < cutoff_time:

                file_path.unlink()

                print(
                    f"Removed old file: {file_path}"
                )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "Sri Lanka 24-Hour Weather Data Pipeline"
    )

    print(
        "=========================================="
    )

    # 1. Download report
    pdf_bytes = download_report()

    # 2. Read actual report date
    report_date = extract_report_date(
        pdf_bytes
    )

    print(
        f"Report date: {report_date}"
    )

    # 3. Extract observations
    df = parse_weather_report(
        pdf_bytes,
        report_date
    )

    print(
        f"Extracted {len(df)} observations."
    )

    # 4. Save PDF + daily CSV + master dataset
    save_data(
        pdf_bytes,
        df,
        report_date
    )

    # 5. Remove files older than 90 days
    cleanup_old_files()

    print(
        "Weather data pipeline completed successfully."
    )


if __name__ == "__main__":
    main()
