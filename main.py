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
    
    print(f"Downloading 24-hour weather report from: {pdf_url}")
    try:
        pdf_res = requests.get(pdf_url)
        pdf_res.raise_for_status()
    except Exception as e:
        print(f"Direct PDF fetch failed: {e}. Trying website fallback...")
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        report_anchor = soup.find('a', string=lambda text: text and '24 Hour Weather Report' in text)
        if report_anchor and report_anchor.get('href'):
            pdf_url = report_anchor['href']
            if not pdf_url.startswith('http'):
                pdf_url = base_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
            pdf_res = requests.get(pdf_url)
            pdf_res.raise_for_status()
        else:
            raise ValueError("Could not locate the 24-Hour Weather Report PDF link.")

    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = f"data/weather_report_{date_str}.xlsx"

    main_stations = []
    hydro_catchment = []
    other_rainfall = []
    
    current_category = "main"

    with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    line_lower = line.lower()
                    # Detect section headings in the text report
                    if "hydro catchment" in line_lower:
                        current_category = "hydro"
                        continue
                    elif "other rainfall" in line_lower or "other stations" in line_lower:
                        current_category = "other"
                        continue
                    
                    # Process lines containing numbers (station data rows)
                    if any(char.isdigit() for char in line):
                        parts = line.split()
                        if len(parts) >= 2:
                            station_record = {
                                "date": date_str,
                                "station": parts[0],
                                "rainfall_mm": parts[1] if len(parts) > 1 else "",
                                "max_temp_c": parts[2] if len(parts) > 2 else "",
                                "min_temp_c": parts[3] if len(parts) > 3 else "",
                                "relative_humidity_pct": parts[4] if len(parts) > 4 else ""
                            }
                            
                            if current_category == "hydro":
                                hydro_catchment.append(station_record)
                            elif current_category == "other":
                                other_rainfall.append(station_record)
                            else:
                                main_stations.append(station_record)

    # Convert to DataFrames
    df_main = pd.DataFrame(main_stations).drop_duplicates(subset=["station"])
    df_hydro = pd.DataFrame(hydro_catchment).drop_duplicates(subset=["station"])
    df_other = pd.DataFrame(other_rainfall).drop_duplicates(subset=["station"])

    # Filter Hydro and Other sheets to contain ONLY 'station' and 'rainfall_mm' (plus date for reference)
    if not df_hydro.empty:
        df_hydro = df_hydro[["date", "station", "rainfall_mm"]]
    if not df_other.empty:
        df_other = df_other[["date", "station", "rainfall_mm"]]

    # Save into separate sheets within the single Excel workbook (.xlsx)
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='Main Stations', index=False)
        df_hydro.to_excel(writer, sheet_name='Hydro Catchment Areas', index=False)
        df_other.to_excel(writer, sheet_name='Other Rainfall Stations', index=False)

    print(f"Successfully saved categorized dataset to Excel sheet workbook: {output_file}")

def cleanup_old_files():
    data_dir = "data"
    now = time.time()
    cutoff_seconds = 90 * 86400  # 90 days
    
    if os.path.exists(data_dir):
        for file_path in glob.glob(f"{data_dir}/weather_report_*.*"):
            if (now - os.path.getmtime(file_path)) > cutoff_seconds:
                os.remove(file_path)
                print(f"Removed old report: {file_path}")

if __name__ == "__main__":
    print("Starting categorized weather extraction...")
    fetch_and_save_weather()
    cleanup_old_files()
    print("Process completed successfully.")
