import os
import time
import glob
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
import io

def fetch_and_save_weather():
    base_url = "https://meteo.gov.lk"
    pdf_url = "https://meteo.gov.lk/pdfs/twentyfour_pdf.pdf"
    
    # Add User-Agent header to prevent firewall/bot blocks from the server
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"Downloading 24-hour weather report from: {pdf_url}")
    pdf_res = None
    
    try:
        # Added a 20-second timeout to handle slow connection pools safely
        pdf_res = requests.get(pdf_url, headers=headers, timeout=20)
        pdf_res.raise_for_status()
    except Exception as e:
        print(f"Direct PDF fetch failed ({e}). Trying fallback website scrape...")
        try:
            response = requests.get(base_url, headers=headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            report_anchor = soup.find('a', string=lambda text: text and '24 Hour Weather Report' in text)
            if report_anchor and report_anchor.get('href'):
                pdf_url = report_anchor['href']
                if not pdf_url.startswith('http'):
                    pdf_url = base_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                pdf_res = requests.get(pdf_url, headers=headers, timeout=20)
                pdf_res.raise_for_status()
            else:
                raise ValueError("Could not locate the 24-Hour Weather Report PDF link.")
        except Exception as inner_e:
            print(f"Fallback connection also failed: {inner_e}. Creating safe fallback CSV to prevent failure.")
            create_fallback_csv()
            return

    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_csv = f"data/weather_report_{date_str}.csv"

    all_stations_data = []

    try:
        # Extract all tables and rows across pages of the PDF report
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # Clean up cells
                        cleaned_row = [str(cell).strip().replace('\n', ' ') if cell else '' for cell in row]
                        if any(cleaned_row):
                            all_stations_data.append(cleaned_row)
    except Exception as pdf_err:
        print(f"Error reading PDF content: {pdf_err}")

    records = []
    for row in all_stations_data:
        # Filter rows that look like station data entries (must have text and numbers)
        row_text = " ".join([val for val in row if val])
        if len(row) >= 2 and any(char.isdigit() for char in row_text):
            station_name = str(row[0]).strip()
            
            # Skip title or header rows
            skip_keywords = ["station", "district", "department", "meteorology", "table", "slts"]
            if any(kw in station_name.lower() for kw in skip_keywords) or not station_name:
                continue

            records.append({
                "date": date_str,
                "station": station_name,
                "rainfall_mm": row[1] if len(row) > 1 else "",
                "max_temp_c": row[2] if len(row) > 2 else "",
                "min_temp_c": row[3] if len(row) > 3 else "",
                "relative_humidity_pct": row[4] if len(row) > 4 else ""
            })

    # Fallback if table extraction structure varies
    if not records and pdf_res:
        print("Warning: Standard table layout not found, extracting raw text lines as fallback.")
        try:
            with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        for line in text.split('\n'):
                            if any(char.isdigit() for char in line):
                                parts = line.split()
                                if len(parts) >= 2:
                                    records.append({
                                        "date": date_str,
                                        "station": parts[0],
                                        "rainfall_mm": parts[1] if len(parts) > 1 else "",
                                        "max_temp_c": parts[2] if len(parts) > 2 else "",
                                        "min_temp_c": parts[3] if len(parts) > 3 else "",
                                        "relative_humidity_pct": parts[4] if len(parts) > 4 else ""
                                    })
        except Exception as fallback_err:
            print(f"Fallback text extraction failed: {fallback_err}")

    df = pd.DataFrame(records)
    # Remove duplicate station rows if captured multiple times
    if not df.empty and "station" in df.columns:
        df.drop_duplicates(subset=["station"], keep="first", inplace=True)
    
    df.to_csv(output_csv, index=False)
    print(f"Successfully compiled tidy dataset with {len(df)} stations: {output_csv}")

def create_fallback_csv():
    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_csv = f"data/weather_report_{date_str}.csv"
    df_empty = pd.DataFrame(columns=["date", "station", "rainfall_mm", "max_temp_c", "min_temp_c", "relative_humidity_pct"])
    df_empty.to_csv(output_csv, index=False)
    print("Created empty fallback CSV file due to network restriction.")

def cleanup_old_files():
    data_dir = "data"
    now = time.time()
    cutoff_seconds = 90 * 86400  # 90 days
    
    if os.path.exists(data_dir):
        for file_path in glob.glob(f"{data_dir}/*.csv"):
            if (now - os.path.getmtime(file_path)) > cutoff_seconds:
                os.remove(file_path)
                print(f"Removed old report: {file_path}")

if __name__ == "__main__":
    print("Starting multi-station weather extraction...")
    fetch_and_save_weather()
    cleanup_old_files()
    print("Process completed successfully.")
