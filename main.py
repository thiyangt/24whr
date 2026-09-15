import os
import requests
import pandas as pd
from datetime import datetime

# Ensure the output directory exists
os.makedirs("data", exist_ok=True)

def run_scraper():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] Starting weather collection...")

    # Define path for daily raw or tidy output
    output_file = "data/weather_tidy.csv"

    # Minimal test payload - replace/expand with your meteo.gov.lk scraping logic
    data = [{
        "date": today,
        "status": "Scraper executed successfully"
    }]
    
    df = pd.DataFrame(data)
    
    # Append data to CSV if it exists, otherwise create new file
    file_exists = os.path.exists(output_file)
    df.to_csv(output_file, mode="a", index=False, header=not file_exists)
    print(f"[{today}] Data saved successfully to {output_file}")

if __name__ == "__main__":
    run_scraper()
