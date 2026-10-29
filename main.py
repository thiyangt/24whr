import os
import re
import time
from io import BytesIO
from datetime import datetime

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://meteo.gov.lk"
PDF_URL = "http://meteo.gov.lk/pdfs/twentyfour_pdf.pdf"

DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")
DAILY_DIR = os.path.join(DATA_DIR, "daily")

MASTER_FILE = os.path.join(DATA_DIR, "weather_tidy.csv")

RETENTION_DAYS = 90


# Browser-like headers help reduce the chance of simple
# bot/firewall blocking.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# DIRECTORY SETUP
# ============================================================

def create_directories():
    """
    Create the required data directories if they do not exist.
    """

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DAILY_DIR, exist_ok=True)

    print("Data directories are ready.")


# ============================================================
# DOWNLOAD WEATHER REPORT
# ============================================================

def download_report():
    """
    Download the latest 24-hour weather report PDF.

    The function:
    1. Tries the direct PDF URL three times.
    2. If that fails, connects to the official website.
    3. Attempts to find the latest 24-hour report link.
    4. Downloads the PDF from the discovered URL.

    Returns:
        bytes: PDF file content.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    # --------------------------------------------------------
    # Attempt 1: Direct PDF URL
    # --------------------------------------------------------

    print("=" * 70)
    print("STEP 1: Downloading the 24-hour weather report")
    print("=" * 70)

    for attempt in range(1, 4):

        try:
            print(
                f"Attempt {attempt}/3: "
                f"Connecting to {PDF_URL}"
            )

            response = session.get(
                PDF_URL,
                timeout=(15, 60)
            )

            response.raise_for_status()

            # Basic validation to make sure the response
            # actually contains something resembling a PDF.
            if len(response.content) < 1000:
                raise RuntimeError(
                    "Downloaded response is too small to be a valid PDF."
                )

            # Check PDF signature when available.
            if not response.content.startswith(b"%PDF"):
                print(
                    "Warning: response does not start with the "
                    "usual PDF signature."
                )

            print(
                f"Download successful. "
                f"Received {len(response.content):,} bytes."
            )

            return response.content

        except requests.exceptions.RequestException as error:

            print(
                f"Attempt {attempt}/3 failed: {error}"
            )

            if attempt < 3:
                wait_seconds = attempt * 10

                print(
                    f"Waiting {wait_seconds} seconds "
                    f"before retrying..."
                )

                time.sleep(wait_seconds)

        except Exception as error:

            print(
                f"Attempt {attempt}/3 failed: {error}"
            )

            if attempt < 3:
                wait_seconds = attempt * 10

                print(
                    f"Waiting {wait_seconds} seconds "
                    f"before retrying..."
                )

                time.sleep(wait_seconds)

    # --------------------------------------------------------
    # Attempt 2: Official website fallback
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STEP 2: Trying the official website as a fallback")
    print("=" * 70)

    try:

        print(f"Connecting to: {BASE_URL}")

        response = session.get(
            BASE_URL,
            timeout=(15, 60)
        )

        response.raise_for_status()

        print("Official website loaded successfully.")

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        report_url = None

        # ----------------------------------------------------
        # Search for a link whose text contains
        # "24 hour weather report"
        # ----------------------------------------------------

        for link in soup.find_all("a", href=True):

            link_text = link.get_text(
                " ",
                strip=True
            ).lower()

            href = link["href"]

            if "24 hour weather report" in link_text:

                report_url = href

                print(
                    "Found 24-hour weather report link "
                    "from website."
                )

                break

        # ----------------------------------------------------
        # If not found, search for the known PDF filename.
        # ----------------------------------------------------

        if report_url is None:

            for link in soup.find_all("a", href=True):

                href = link["href"]

                if "twentyfour_pdf.pdf" in href.lower():

                    report_url = href

                    print(
                        "Found twentyfour_pdf.pdf "
                        "link from website."
                    )

                    break

        # ----------------------------------------------------
        # Stop if no report link was found.
        # ----------------------------------------------------

        if report_url is None:

            raise RuntimeError(
                "Could not locate the 24-hour weather report "
                "PDF link on the official website."
            )

        # Convert relative URL to absolute URL.
        report_url = requests.compat.urljoin(
            BASE_URL,
            report_url
        )

        print(
            f"Downloading report from discovered URL:\n"
            f"{report_url}"
        )

        response = session.get(
            report_url,
            timeout=(15, 60)
        )

        response.raise_for_status()

        if len(response.content) < 1000:

            raise RuntimeError(
                "Downloaded fallback response is too small "
                "to be a valid PDF."
            )

        print(
            f"Fallback download successful. "
            f"Received {len(response.content):,} bytes."
        )

        return response.content

    except Exception as error:

        raise RuntimeError(
            "Unable to download the 24-hour weather report "
            "from the Department of Meteorology website. "
            "The GitHub Actions runner may be unable to "
            "connect to the website."
        ) from error


# ============================================================
# EXTRACT REPORT DATE
# ============================================================

def extract_report_date(pdf_bytes):
    """
    Extract the actual report date from the PDF.

    The Department of Meteorology report commonly contains
    dates in formats such as:

        2026.10.28
        2026.10.27

    Returns:
        str: Date in YYYY-MM-DD format.

    Raises:
        ValueError: If a report date cannot be found.
    """

    print()
    print("=" * 70)
    print("STEP 3: Extracting report date")
    print("=" * 70)

    date_patterns = [
        r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b",
    ]

    all_dates = []

    with pdfplumber.open(
        BytesIO(pdf_bytes)
    ) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

            text = page.extract_text() or ""

            for pattern in date_patterns:

                matches = re.findall(
                    pattern,
                    text
                )

                for match in matches:

                    try:

                        year = int(match[0])
                        month = int(match[1])
                        day = int(match[2])

                        date_object = datetime(
                            year,
                            month,
                            day
                        )

                        all_dates.append(
                            date_object
                        )

                    except ValueError:
                        continue

    if not all_dates:

        raise ValueError(
            "Could not find a valid report date in the PDF."
        )

    # Usually the first relevant date is the report date.
    report_date = min(all_dates)

    date_string = report_date.strftime(
        "%Y-%m-%d"
    )

    print(
        f"Report date detected: {date_string}"
    )

    return date_string


# ============================================================
# CELL CLEANING
# ============================================================

def clean_cell(value):
    """
    Clean a PDF table cell.
    """

    if value is None:
        return ""

    value = str(value)

    # Replace line breaks with spaces.
    value = value.replace("\n", " ")

    # Remove repeated whitespace.
    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# NUMERIC CONVERSION
# ============================================================

def to_number(value):
    """
    Convert a PDF cell into a numeric value.

    Examples:
        '31.2' -> 31.2
        '31.2 C' -> 31.2
        '-' -> None
        'T' -> 0.0

    Returns:
        float or None
    """

    if value is None:
        return None

    value = clean_cell(value)

    if value == "":
        return None

    value_upper = value.upper()

    # Trace rainfall is conventionally treated as zero
    # for the numeric tidy dataset.
    if value_upper in {
        "T",
        "TRACE"
    }:
        return 0.0

    # Missing values.
    if value_upper in {
        "-",
        "--",
        "NA",
        "N/A",
        "NAN"
    }:
        return None

    # Extract the first decimal/integer number.
    match = re.search(
        r"-?\d+(?:\.\d+)?",
        value
    )

    if not match:
        return None

    try:
        return float(match.group(0))

    except ValueError:
        return None


# ============================================================
# STATION NAME CLEANING
# ============================================================

def clean_station_name(value):
    """
    Clean station names extracted from the PDF.
    """

    value = clean_cell(value)

    if not value:
        return ""

    # Remove leading numbering such as:
    # 1. Colombo
    # 01 Colombo
    # 1 Colombo
    value = re.sub(
        r"^\s*\d+\s*[\.\)]?\s*",
        "",
        value
    )

    return value.strip()


# ============================================================
# HEADER DETECTION
# ============================================================

def looks_like_header(row):
    """
    Determine whether a PDF table row is a header row.
    """

    row_text = " ".join(
        clean_cell(cell).lower()
        for cell in row
        if cell is not None
    )

    header_keywords = [
        "station",
        "maximum temperature",
        "minimum temperature",
        "max temperature",
        "min temperature",
        "rainfall",
        "district",
        "weather",
        "date",
        "time",
    ]

    matches = sum(
        keyword in row_text
        for keyword in header_keywords
    )

    return matches >= 2


# ============================================================
# INVALID STATION NAME DETECTION
# ============================================================

def is_invalid_station_name(station):
    """
    Check whether a string is probably a title/header
    rather than an actual weather station.
    """

    if not station:
        return True

    station_lower = station.lower()

    invalid_keywords = [
        "station",
        "district",
        "maximum",
        "minimum",
        "temperature",
        "rainfall",
        "weather report",
        "department of meteorology",
        "meteorological",
        "daily rainfall",
        "24 hour",
        "time",
        "date",
        "slts",
        "average",
        "total",
    ]

    for keyword in invalid_keywords:

        if keyword in station_lower:
            return True

    return False


# ============================================================
# PARSE MAIN WEATHER TABLE
# ============================================================

def parse_weather_report(pdf_bytes, report_date):
    """
    Extract station-level meteorological observations.

    Expected main table structure is approximately:

        Station | Maximum Temperature | Minimum Temperature | Rainfall

    The function also attempts to handle small variations
    in table layout.
    """

    print()
    print("=" * 70)
    print("STEP 4: Extracting weather observations")
    print("=" * 70)

    records = []

    with pdfplumber.open(
        BytesIO(pdf_bytes)
    ) as pdf:

        print(
            f"PDF contains {len(pdf.pages)} page(s)."
        )

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

            print(
                f"Processing page {page_number}..."
            )

            try:

                tables = page.extract_tables()

            except Exception as error:

                print(
                    f"Could not extract tables from "
                    f"page {page_number}: {error}"
                )

                continue

            for table_number, table in enumerate(
                tables,
                start=1
            ):

                if not table:
                    continue

                for row in table:

                    if not row:
                        continue

                    cleaned_row = [
                        clean_cell(cell)
                        for cell in row
                    ]

                    # Remove completely empty rows.
                    if not any(cleaned_row):
                        continue

                    # Ignore header rows.
                    if looks_like_header(
                        cleaned_row
                    ):
                        continue

                    # ------------------------------------------------
                    # We are mainly interested in rows containing
                    # at least 4 columns:
                    #
                    # Station
                    # Max temperature
                    # Min temperature
                    # Rainfall
                    # ------------------------------------------------

                    if len(cleaned_row) < 4:
                        continue

                    station = clean_station_name(
                        cleaned_row[0]
                    )

                    if is_invalid_station_name(
                        station
                    ):
                        continue

                    max_temp = to_number(
                        cleaned_row[1]
                    )

                    min_temp = to_number(
                        cleaned_row[2]
                    )

                    rainfall = to_number(
                        cleaned_row[3]
                    )

                    # A valid weather row should normally contain
                    # at least one numeric meteorological value.
                    numeric_values = [
                        max_temp,
                        min_temp,
                        rainfall
                    ]

                    if all(
                        value is None
                        for value in numeric_values
                    ):
                        continue

                    records.append(
                        {
                            "report_date": report_date,
                            "station": station,
                            "max_temp_c": max_temp,
                            "min_temp_c": min_temp,
                            "rainfall_mm": rainfall,
                        }
                    )

    # ------------------------------------------------------------
    # Remove duplicate station/date combinations.
    # ------------------------------------------------------------

    if records:

        df = pd.DataFrame(records)

        df.drop_duplicates(
            subset=[
                "report_date",
                "station"
            ],
            keep="first",
            inplace=True
        )

    else:

        df = pd.DataFrame(
            columns=[
                "report_date",
                "station",
                "max_temp_c",
                "min_temp_c",
                "rainfall_mm",
            ]
        )

    print(
        f"Extracted {len(df)} station observations."
    )

    return df


# ============================================================
# FALLBACK TEXT EXTRACTION
# ============================================================

def fallback_text_extraction(
    pdf_bytes,
    report_date
):
    """
    Fallback parser for situations where pdfplumber's
    table extraction does not work.

    This reads the raw text line-by-line and attempts
    to identify rows containing at least three numeric
    weather observations.
    """

    print()
    print(
        "Standard table extraction returned no records."
    )

    print(
        "Trying fallback text extraction..."
    )

    records = []

    with pdfplumber.open(
        BytesIO(pdf_bytes)
    ) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

            text = page.extract_text()

            if not text:
                continue

            for line in text.splitlines():

                line = clean_cell(line)

                if not line:
                    continue

                # Ignore obvious headings.
                if looks_like_header([line]):
                    continue

                # Find numeric values.
                numbers = re.findall(
                    r"-?\d+(?:\.\d+)?",
                    line
                )

                # We need at least three numeric values
                # for max temperature, min temperature
                # and rainfall.
                if len(numbers) < 3:
                    continue

                parts = line.split()

                if len(parts) < 4:
                    continue

                # Try to identify the numeric portion.
                numeric_positions = []

                for index, part in enumerate(parts):

                    if re.fullmatch(
                        r"-?\d+(?:\.\d+)?",
                        part
                    ):

                        numeric_positions.append(index)

                if len(numeric_positions) < 3:
                    continue

                first_numeric_index = (
                    numeric_positions[0]
                )

                station_parts = parts[
                    :first_numeric_index
                ]

                station = clean_station_name(
                    " ".join(station_parts)
                )

                if is_invalid_station_name(
                    station
                ):
                    continue

                try:

                    max_temp = float(
                        parts[
                            numeric_positions[0]
                        ]
                    )

                    min_temp = float(
                        parts[
                            numeric_positions[1]
                        ]
                    )

                    rainfall = float(
                        parts[
                            numeric_positions[2]
                        ]
                    )

                except (ValueError, IndexError):

                    continue

                records.append(
                    {
                        "report_date": report_date,
                        "station": station,
                        "max_temp_c": max_temp,
                        "min_temp_c": min_temp,
                        "rainfall_mm": rainfall,
                    }
                )

    if records:

        df = pd.DataFrame(records)

        df.drop_duplicates(
            subset=[
                "report_date",
                "station"
            ],
            keep="first",
            inplace=True
        )

        print(
            f"Fallback extraction found "
            f"{len(df)} observations."
        )

        return df

    print(
        "Fallback text extraction also found no records."
    )

    return pd.DataFrame(
        columns=[
            "report_date",
            "station",
            "max_temp_c",
            "min_temp_c",
            "rainfall_mm",
        ]
    )


# ============================================================
# SAVE RAW PDF
# ============================================================

def save_raw_pdf(
    pdf_bytes,
    report_date
):
    """
    Save the original PDF for reproducibility/audit purposes.
    """

    filename = (
        f"weather_report_{report_date}.pdf"
    )

    filepath = os.path.join(
        RAW_DIR,
        filename
    )

    with open(
        filepath,
        "wb"
    ) as file:

        file.write(pdf_bytes)

    print(
        f"Raw PDF saved: {filepath}"
    )

    return filepath


# ============================================================
# SAVE DAILY CSV
# ============================================================

def save_daily_csv(
    df,
    report_date
):
    """
    Save one tidy CSV file for the report date.
    """

    filename = (
        f"weather_report_{report_date}.csv"
    )

    filepath = os.path.join(
        DAILY_DIR,
        filename
    )

    df.to_csv(
        filepath,
        index=False
    )

    print(
        f"Daily CSV saved: {filepath}"
    )

    return filepath


# ============================================================
# UPDATE MASTER TIDY DATASET
# ============================================================

def update_master_dataset(df):
    """
    Add the latest observations to the master tidy dataset.

    If the same report date and station already exist,
    the newer observation replaces the older one.
    """

    print()
    print("=" * 70)
    print("STEP 5: Updating master tidy dataset")
    print("=" * 70)

    if df.empty:

        raise RuntimeError(
            "No observations were extracted. "
            "Master dataset will not be modified."
        )

    if os.path.exists(
        MASTER_FILE
    ):

        try:

            existing_df = pd.read_csv(
                MASTER_FILE
            )

            print(
                f"Existing master dataset contains "
                f"{len(existing_df)} rows."
            )

        except Exception as error:

            print(
                f"Could not read existing master dataset: "
                f"{error}"
            )

            existing_df = pd.DataFrame()

    else:

        existing_df = pd.DataFrame()

    # Combine old and new observations.
    combined_df = pd.concat(
        [
            existing_df,
            df
        ],
        ignore_index=True
    )

    # Remove duplicate observations.
    #
    # Keep the LAST record so that if today's workflow
    # runs more than once, the latest extraction is used.
    combined_df.drop_duplicates(
        subset=[
            "report_date",
            "station"
        ],
        keep="last",
        inplace=True
    )

    # Sort chronologically.
    combined_df.sort_values(
        by=[
            "report_date",
            "station"
        ],
        inplace=True
    )

    # Reset index.
    combined_df.reset_index(
        drop=True,
        inplace=True
    )

    # Save master dataset.
    combined_df.to_csv(
        MASTER_FILE,
        index=False
    )

    print(
        f"Master tidy dataset updated: {MASTER_FILE}"
    )

    print(
        f"Total observations in master dataset: "
        f"{len(combined_df)}"
    )

    return combined_df


# ============================================================
# CLEAN OLD FILES
# ============================================================

def cleanup_old_files():
    """
    Remove raw PDFs and daily CSV files older than 90 days.

    The master weather_tidy.csv is NOT deleted.
    """

    print()
    print("=" * 70)
    print("STEP 6: Cleaning files older than 90 days")
    print("=" * 70)

    cutoff_seconds = (
        RETENTION_DAYS * 24 * 60 * 60
    )

    current_time = time.time()

    removed_count = 0

    directories = [
        RAW_DIR,
        DAILY_DIR
    ]

    for directory in directories:

        if not os.path.exists(directory):
            continue

        for filename in os.listdir(directory):

            filepath = os.path.join(
                directory,
                filename
            )

            if not os.path.isfile(filepath):
                continue

            try:

                modified_time = os.path.getmtime(
                    filepath
                )

                age_seconds = (
                    current_time - modified_time
                )

                if age_seconds > cutoff_seconds:

                    os.remove(filepath)

                    removed_count += 1

                    print(
                        f"Removed old file: {filepath}"
                    )

            except OSError as error:

                print(
                    f"Could not remove {filepath}: "
                    f"{error}"
                )

    if removed_count == 0:

        print(
            "No files older than 90 days were found."
        )

    else:

        print(
            f"Removed {removed_count} old file(s)."
        )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    """
    Main weather data extraction pipeline.
    """

    print()
    print("=" * 70)
    print("SRI LANKA 24-HOUR WEATHER DATA EXTRACTION")
    print("=" * 70)

    print(
        "Starting weather data extraction..."
    )

    # --------------------------------------------------------
    # 1. Create directories
    # --------------------------------------------------------

    create_directories()

    # --------------------------------------------------------
    # 2. Download latest PDF
    # --------------------------------------------------------

    pdf_bytes = download_report()

    # --------------------------------------------------------
    # 3. Extract actual report date
    # --------------------------------------------------------

    report_date = extract_report_date(
        pdf_bytes
    )

    # --------------------------------------------------------
    # 4. Save raw PDF
    # --------------------------------------------------------

    save_raw_pdf(
        pdf_bytes,
        report_date
    )

    # --------------------------------------------------------
    # 5. Extract weather data
    # --------------------------------------------------------

    df = parse_weather_report(
        pdf_bytes,
        report_date
    )

    # --------------------------------------------------------
    # 6. If standard extraction fails, use fallback parser
    # --------------------------------------------------------

    if df.empty:

        df = fallback_text_extraction(
            pdf_bytes,
            report_date
        )

    # --------------------------------------------------------
    # 7. Do not continue if no data was extracted.
    # --------------------------------------------------------

    if df.empty:

        raise RuntimeError(
            "No weather observations could be extracted "
            "from the PDF. The dataset was NOT updated."
        )

    # --------------------------------------------------------
    # 8. Ensure correct column order
    # --------------------------------------------------------

    expected_columns = [
        "report_date",
        "station",
        "max_temp_c",
        "min_temp_c",
        "rainfall_mm",
    ]

    df = df[
        expected_columns
    ]

    # --------------------------------------------------------
    # 9. Save daily CSV
    # --------------------------------------------------------

    save_daily_csv(
        df,
        report_date
    )

    # --------------------------------------------------------
    # 10. Update master tidy dataset
    # --------------------------------------------------------

    update_master_dataset(
        df
    )

    # --------------------------------------------------------
    # 11. Remove files older than 90 days
    # --------------------------------------------------------

    cleanup_old_files()

    # --------------------------------------------------------
    # 12. Display summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EXTRACTION COMPLETED SUCCESSFULLY")
    print("=" * 70)

    print(
        f"Report date : {report_date}"
    )

    print(
        f"Stations extracted : {len(df)}"
    )

    print(
        f"Daily file : "
        f"{DAILY_DIR}/weather_report_{report_date}.csv"
    )

    print(
        f"Master dataset : {MASTER_FILE}"
    )

    print("=" * 70)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
