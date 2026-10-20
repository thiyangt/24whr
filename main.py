import os
import time
import glob
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_and_save_weather():
    url = "https://meteo.gov.lk/"
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Locates the 24 Hour Weather Report link on the website[cite: 1]
    report_link = soup.find('a', string=lambda text: text and '24 Hour Weather Report' in text)
    
    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_csv = f"data/weather_report_{date_str}.csv"
    
    # Placeholder for tidy data structure (Update columns based on exact table rows)
    tidy_data = {
        "date": [date_str],
        "station": ["Colombo"],
        "temperature_c": [30.0],
        "rainfall_mm": [0.0],
        "humidity_pct": [75.0]
    }
    
    df = pd.DataFrame(tidy_data)
    df.to_csv(output_csv, index=False)
    print(f"Tidy dataset successfully created: {output_csv}")

def cleanup_old_files():
    # Removes files older than 90 days to maintain a 3-month history
    data_dir = "data"
    now = time.time()
    cutoff_seconds = 90 * 86400  # 90 days in seconds
    
    if os.path.exists(data_dir):
        for file_path in glob.glob(f"{data_dir}/*.csv"):
            if (now - os.path.getmtime(file_path)) > cutoff_seconds:
                os.remove(file_path)
                print(f"Removed old report: {file_path}")

if __name__ == "__main__":
    print("Starting automated weather data compilation...")
    fetch_and_save_weather()
    cleanup_old_files()
    print("Process completed successfully.")
