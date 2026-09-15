import os
import re
import requests
import pdfplumber
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# Setup headers to prevent site blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://meteo.gov.lk"
DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "weather_tidy.csv")

os.makedirs(DATA_DIR, exist_ok=True)


def get_latest_report_pdf_url() -> str:
    """Finds the link for the latest daily weather report PDF."""
    print("Fetching meteo.gov.lk homepage...")
    response = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Search for PDF anchor tags containing report keywords
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if ".pdf" in href.lower() and any(
            k in href.lower() for k in ["daily", "weather", "report", "observation"]
        ):
            if href.startswith("http"):
                return href
            return f"{BASE_URL}/{href.lstrip('/')}"

    # Fallback search for any active PDF on the main page if named differently
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if ".pdf" in href.lower():
            if href.startswith("http"):
                return href
            return f"{BASE_URL}/{href.lstrip('/')}"

    raise ValueError("Could not locate daily weather PDF link on meteo.gov.lk")


def extract_tidy_data_from_pdf(pdf_path: str, report_date: str) -> pd.DataFrame:
    """Parses station tables from the PDF into a tidy pandas DataFrame."""
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Filter empty or header rows
                    if not row or len(row) < 3:
                        continue

                    # Basic cleanup of row strings
                    clean_row = [
                        str(cell).strip() if cell else "" for cell in row
                    ]

                    # Detect station data lines (non-empty name + numeric measurements)
                    station_name = clean_row[0]
                    if (
                        station_name
                        and not station_name.lower().startswith("station")
                    ):
                        records.append(
                            {
                                "date": report_date,
                                "station": station_name,
                                "raw_metrics": " | ".join(clean_row[1:]),
                            }
                        )

    if not records:
        # Fallback raw text capture if standard tables aren't found
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(
                [
                    page.extract_text()
                    for page in pdf.pages
                    if page.extract_text()
                ]
            )
            records.append(
                {
                    "date": report_date,
                    "station": "Full_Report_Text",
                    "raw_metrics": full_text[:500].replace("\n", " "),
                }
            )

    return pd.DataFrame(records)


def run_pipeline():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today_str}] Starting collection task...")

    # 1. Locate PDF
    pdf_url = get_latest_report_pdf_url()
    print(f"Found report PDF URL: {pdf_url}")

    # 2. Download raw PDF
    temp_pdf_path = os.path.join(DATA_DIR, "temp_report.pdf")
    pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=30)
    pdf_resp.raise_for_status()

    with open(temp_pdf_path, "wb") as f:
        f.write(pdf_resp.content)

    # 3. Parse content into Tidy DataFrame
    df_new = extract_tidy_data_from_pdf(temp_pdf_path, today_str)

    # 4. Save to CSV
    file_exists = os.path.exists(CSV_PATH)
    df_new.to_csv(CSV_PATH, mode="a", index=False, header=not file_exists)
    print(f"[{today_str}] Added {len(df_new)} weather records to {CSV_PATH}")

    # Cleanup temporary PDF file
    if os.path.exists(temp_pdf_path):
        os.remove(temp_pdf_path)


if __name__ == "__main__":
    run_pipeline()
