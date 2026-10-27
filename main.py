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
        print(f"Direct PDF fetch failed: {e}. Trying fallback...")
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
    
    current_section = "main"

    with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
        for page in pdf.pages:
            # Extract structured tables using pdfplumber's built-in table finder
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Clean cells
                    cells = [str(c).strip().replace('\n', ' ') if c else '' for c in row]
                    row_text = " ".join(cells).lower()

                    # Detect section shifts based on PDF headers
                    if "hydro catchment" in row_text:
                        current_section = "hydro"
                        continue
                    elif "other rainfall" in row_text or "other stations" in row_text:
                        current_section = "other"
                        continue

                    # Process table rows based on current active section
                    if current_section == "main":
                        # Main station table structure: [Station, Min Temp, Max Temp, Rainfall]
                        if len(cells) >= 4 and any(char.isdigit() for char in row_text):
                            station_name = cells[0]
                            if station_name and not any(kw in station_name.lower() for kw in ["station", "district", "temperature"]):
                                main_stations.append({
                                    "date": date_str,
                                    "station": station_name,
                                    "min_temp_c": cells[1],
                                    "max_temp_c": cells[2],
                                    "rainfall_mm": cells[3]
                                })
                    
                    elif current_section in ["hydro", "other"]:
                        # Side-by-side tables often have 2 pairs of (Station, Rainfall) in a single row
                        # Left side pair (Cols 0 & 1)
                        if len(cells) >= 2 and cells[0] and any(char.isdigit() for char in cells[1]):
                            if not any(kw in cells[0].lower() for kw in ["station", "rainfall", "catchment"]):
                                record = {"date": date_str, "station": cells[0], "rainfall_mm": cells[1]}
                                if current_section == "hydro":
                                    hydro_catchment.append(record)
                                else:
                                    other_rainfall.append(record)
                        
                        # Right side pair (Cols 2 & 3 - handling side-by-side multi-column layout)
                        if len(cells) >= 4 and cells[2] and any(char.isdigit() for char in cells[3]):
                            if not any(kw in cells[2].lower() for kw in ["station", "rainfall", "catchment"]):
                                record = {"date": date_str, "station": cells[2], "rainfall_mm": cells[3]}
                                if current_section == "hydro":
                                    hydro_catchment.append(record)
                                else:
                                    other_rainfall.append(record)

    # Convert to DataFrames and remove duplicates
    df_main = pd.DataFrame(main_stations).drop_duplicates(subset=["station"])
    df_hydro = pd.DataFrame(hydro_catchment).drop_duplicates(subset=["station"])
    df_other = pd.DataFrame(other_rainfall).drop_duplicates(subset=["station"])

    # Ensure Hydro and Other sheets contain STRICTLY station and rainfall data
    if not df_hydro.empty:
        df_hydro = df_hydro[["date", "station", "rainfall_mm"]]
    if not df_other.empty:
        df_other = df_other[["date", "station", "rainfall_mm"]]

    # Save into separate sheets inside the Excel workbook
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='Main Stations', index=False)
        df_hydro.to_excel(writer, sheet_name='Hydro Catchment Areas', index=False)
        df_other.to_excel(writer, sheet_name='Other Rainfall Stations', index=False)

    print(f"Successfully compiled multi-sheet workbook: {output_file}")

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
    print("Starting robust multi-station extraction...")
    fetch_and_save_weather()
    cleanup_old_files()
    print("Process completed successfully.")
