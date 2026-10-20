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
    response = requests.get(base_url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Locate the 24 Hour Weather Report PDF link on meteo.gov.lk
    report_anchor = soup.find('a', string=lambda text: text and '24 Hour Weather Report' in text)
    
    if not report_anchor or not report_anchor.get('href'):
        print("Could not locate 24-Hour Weather Report link directly. Trying alternative fallback endpoint.")
        # Fallback direct path if website updates target anchor
        pdf_url = f"{base_url}/pdfs/land_pdf.pdf"
    else:
        pdf_url = report_anchor['href']
        if not pdf_url.startswith('http'):
            pdf_url = base_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url

    print(f"Downloading report from: {pdf_url}")
    pdf_res = requests.get(pdf_url)
    pdf_res.raise_for_status()

    # Create output directory
    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_csv = f"data/weather_report_{date_str}.csv"

    # Extract tables for ALL stations from the PDF
    all_rows = []
    with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Clean up extracted cell text
                    cleaned_row = [str(cell).strip().replace('\n', ' ') if cell else '' for cell in row]
                    # Ensure row has content and isn't empty header artifact
                    if any(cleaned_row):
                        all_rows.append(cleaned_row)

    if not all_rows:
        print("Warning: No tabular rows found in PDF. Storing raw fallback table.")
        # Create default dataframe structure if PDF layout differs on given day
        df = pd.DataFrame(columns=["date", "station", "rainfall_mm", "max_temp_c", "min_temp_c", "relative_humidity_pct"])
    else:
        # Convert extracted rows into Dataframe
        raw_df = pd.DataFrame(all_rows)
        
        # Clean up header & rows to retain station observations
        # Drop completely empty columns/rows
        raw_df.dropna(how='all', inplace=True)
        
        # Filter for data rows (ignoring repeated headers/titles)
        # Assuming table columns correspond to: Station, Rainfall, Max Temp, Min Temp, Humidity
        records = []
        for idx, row in raw_df.iterrows():
            row_text = " ".join([str(val) for val in row if val])
            
            # Basic validation to check if the line contains station weather metrics
            if any(char.isdigit() for char in row_text) and len(row) >= 2:
                station_name = str(row[0]).strip()
                
                # Filter out pure heading rows
                if "station" in station_name.lower() or "district" in station_name.lower() or "department" in station_name.lower():
                    continue

                records.append({
                    "date": date_str,
                    "station": station_name,
                    "rainfall_mm": row[1] if len(row) > 1 else None,
                    "max_temp_c": row[2] if len(row) > 2 else None,
                    "min_temp_c": row[3] if len(row) > 3 else None,
                    "relative_humidity_pct": row[4] if len(row) > 4 else None
                })
        
        df = pd.DataFrame(records)

    # Clean up tidy data columns
    df["date"] = date_str
    df.to_csv(output_csv, index=False)
    print(f"Successfully saved all stations ({len(df)} rows) into tidy dataset: {output_csv}")

def cleanup_old_files():
    # Maintains 3-month (90 days) rolling history
    data_dir = "data"
    now = time.time()
    cutoff_seconds = 90 * 86400  # 90 days in seconds
    
    if os.path.exists(data_dir):
        for file_path in glob.glob(f"{data_dir}/*.csv"):
            if (now - os.path.getmtime(file_path)) > cutoff_seconds:
                os.remove(file_path)
                print(f"Removed old report: {file_path}")

if __name__ == "__main__":
    print("Starting automated weather data extraction for all stations...")
    fetch_and_save_weather()
    cleanup_old_files()
    print("Process completed successfully.")
