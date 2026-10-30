# Automated 24-Hour Weather Report Compilation and Tidy Dataset Generation

## 1. Introduction

This project develops a Python-based data collection and processing system for compiling the 24-hour weather reports published by the Department of Meteorology of Sri Lanka at [https://meteo.gov.lk/](https://meteo.gov.lk/).

The main purpose of the project is to automate the extraction of meteorological observations from the published 24-hour weather report PDF files and transform the extracted information into a structured and tidy dataset suitable for further analysis.

The system is designed to collect daily weather observations for a period of approximately three months. The collected raw reports are retained separately, while processed daily datasets are generated in CSV format and combined into a master tidy dataset.

The project uses Python libraries including `requests`, `BeautifulSoup`, `pdfplumber`, and `pandas` for data acquisition, PDF processing, data cleaning, and dataset generation.

The project also uses GitHub for version control and GitHub Actions for automated software testing and validation.

---

## 2. Problem Statement

The 24-hour weather information is published as daily PDF reports. Although the reports contain useful meteorological observations, the information is not directly available as a structured machine-readable dataset.

Manual collection and extraction of these reports can be time-consuming and error-prone.

Therefore, this project aims to develop a reusable Python-based solution that can:

1. Retrieve the published 24-hour weather report.
2. Extract relevant meteorological observations from the PDF.
3. Clean and standardize the extracted values.
4. Generate a structured daily CSV file.
5. Combine daily observations into a master tidy dataset.
6. Maintain the collected data for approximately three months.
7. Support automated execution and reproducible data processing.

---

## 3. Objectives

### 3.1 Main Objective

To develop a Python package that automates the extraction, cleaning, and compilation of Sri Lankan 24-hour weather report data into a tidy dataset.

### 3.2 Specific Objectives

- To automatically retrieve the daily 24-hour weather report published by the Department of Meteorology of Sri Lanka.
- To extract meteorological observations from the PDF reports.
- To identify and process relevant weather variables such as:
  - Weather station
  - Maximum temperature
  - Minimum temperature
  - Daily rainfall
- To clean and standardize extracted values.
- To generate a separate CSV file for each reporting day.
- To maintain a consolidated master dataset containing observations from multiple days.
- To implement duplicate detection and removal when updating the master dataset.
- To maintain raw PDF reports separately from processed data.
- To retain the required data collection period of approximately three months.
- To develop automated validation and testing using GitHub Actions.
- To provide a reproducible workflow that can be extended for future automated data collection.

---

## 4. Project Workflow

The overall workflow of the proposed system is shown below:

```
        Department of Meteorology
                    │
                    ▼
       24-Hour Weather Report PDF
                    │
                    ▼
          Data Acquisition Layer
                    │
                    ▼
             Raw PDF Storage
                    │
                    ▼
             PDF Extraction
                    │
                    ▼
            Data Cleaning
                    │
                    ▼
       Data Validation / Formatting
                    │
                    ▼
          Daily CSV Generation
                    │
                    ▼
       Master Dataset Update
                    │
                    ▼
          Tidy Weather Dataset
                    │
                    ▼
              Git Repository
                    │
                    ▼
       GitHub Actions Validation
```

### Workflow Description

#### Step 1 – Data Acquisition

The system attempts to retrieve the latest 24-hour weather report published by the Department of Meteorology.

The downloader includes retry handling and a fallback mechanism for accessing the official website.

#### Step 2 – Raw Data Storage

The downloaded PDF is retained in the raw data directory.

```
data/
└── raw/
```

Maintaining the raw source files allows the extracted information to be traced back to the original published report.

#### Step 3 – PDF Extraction

The PDF report is processed using `pdfplumber`.

The extraction process identifies the meteorological observation table and retrieves relevant fields.

#### Step 4 – Data Cleaning

Extracted values are cleaned and standardized.

The current processing includes:

- Removal of unnecessary whitespace.
- Conversion of numerical observations into numeric data types.
- Cleaning of weather station names.
- Detection of invalid or header-like rows.
- Handling of missing or malformed values.

#### Step 5 – Daily Dataset Generation

After extraction and cleaning, the observations are stored as a daily CSV file.

Example:

```
data/daily/2026-10-30.csv
```

#### Step 6 – Master Dataset Generation

The daily dataset is incorporated into a consolidated dataset:

```
data/weather_tidy.csv
```

Duplicate observations are identified and removed during the update process.

#### Step 7 – Data Retention

The project is designed to maintain approximately 90 days of collected raw and processed files.

Older files can be removed automatically according to the configured retention period.

#### Step 8 – Validation and Automation

GitHub Actions is used to support automated validation and testing of the Python project.

The data acquisition component is designed to run in an environment that has network access to the Department of Meteorology website.

---

## 5. Data Structure

The processed dataset is designed around the following structure:

| Column | Description |
|---|---|
| `report_date` | Date of the weather report |
| `station` | Meteorological observation station |
| `max_temperature` | Maximum recorded temperature |
| `min_temperature` | Minimum recorded temperature |
| `rainfall` | Daily rainfall measurement |

Example:

```
report_date,station,max_temperature,min_temperature,rainfall
2026-10-30,Colombo,31.2,25.1,12.4
2026-10-30,Kandy,28.4,20.6,5.6
2026-10-30,Katunayake,30.8,24.9,8.2
```

---

## 6. Project Structure

The current repository contains the following major components:

```
.
├── .github/
│   └── workflows/
│       └── daily_scraper.yml
│
├── data/
│   ├── raw/
│   ├── daily/
│   └── weather_tidy.csv
│
├── main.py
├── requirements.txt
└── README.md
```

### Main Components

**`main.py`**

Contains the main data acquisition, extraction, cleaning, storage, and dataset update pipeline.

**`requirements.txt`**

Contains the Python dependencies required by the project.

**`data/raw/`**

Stores downloaded source PDF reports.

**`data/daily/`**

Stores processed daily CSV files.

**`data/weather_tidy.csv`**

Contains the consolidated tidy weather dataset.

**`.github/workflows/`**

Contains GitHub Actions workflow configurations.

---

## 7. Technologies Used

- Python 3.11
- pandas
- requests
- BeautifulSoup
- pdfplumber
- openpyxl
- Git
- GitHub
- GitHub Actions

---

## 8. Installation

Clone the repository:

```
git clone <repository-url>
cd <repository-folder>
```

Install the required Python packages:

```
pip install -r requirements.txt
```

---

## 9. Running the Pipeline

The current pipeline can be executed using:

```
python main.py
```

The program performs the following operations:

```
Download report
      ↓
Extract report date
      ↓
Parse PDF
      ↓
Clean observations
      ↓
Save daily CSV
      ↓
Update master dataset
      ↓
Apply data retention
```

---

## 10. Current Implementation Status

### Completed

- [x] Initial GitHub repository created.
- [x] Python data collection script developed.
- [x] Required Python dependencies identified.
- [x] PDF downloading functionality implemented.
- [x] PDF parsing functionality implemented.
- [x] Weather station extraction implemented.
- [x] Maximum temperature extraction implemented.
- [x] Minimum temperature extraction implemented.
- [x] Daily rainfall extraction implemented.
- [x] Data cleaning functionality implemented.
- [x] Daily CSV generation implemented.
- [x] Master tidy dataset update implemented.
- [x] Duplicate handling implemented.
- [x] Raw and processed data separation implemented.
- [x] 90-day data retention functionality implemented.
- [x] GitHub Actions workflow investigated.
- [x] Network connectivity issue with the external data source investigated.

### In Progress

- [ ] Improve Python package structure.
- [ ] Add automated unit tests.
- [ ] Improve GitHub Actions validation workflow.
- [ ] Expand documentation.
- [ ] Validate the pipeline using a larger collection of historical reports.

### Future Work

- [ ] Implement fully scheduled data collection.
- [ ] Configure a suitable execution environment with access to the data source.
- [ ] Automate daily Git synchronization.
- [ ] Complete three-month continuous data collection.
- [ ] Add additional data quality checks.
- [ ] Add automated monitoring and error reporting.

---

## 11. Technical Challenge Identified

During development, the project encountered a network accessibility issue when the GitHub-hosted execution environment attempted to access the Department of Meteorology website.

DNS resolution of the domain was successful; however, connections to the website from the GitHub-hosted environment timed out.

The source PDF can be accessed successfully from the local development environment.

This issue is therefore considered an execution-environment/network-access limitation rather than a PDF parsing problem.

The project architecture has been designed so that the data acquisition component can be executed in an environment with appropriate network access while GitHub can continue to be used for version control, testing, validation, and documentation.

---

## 12. Reproducibility

The project maintains the source code, dependency definitions, processing logic, and data organization within the GitHub repository.

Raw source reports are separated from processed datasets to support traceability and reproducibility.

The processing pipeline is designed so that the same extraction and cleaning operations can be applied consistently to future reports.

---

## 13. Expected Output

The final system is expected to produce:

1. A collection of raw 24-hour weather report PDFs.
2. A daily CSV file for each report.
3. A consolidated tidy weather dataset.
4. Automated data cleaning and validation.
5. A reproducible Python package.
6. Automated testing through GitHub Actions.
7. Approximately three months of structured weather observations.

---

## 14. Conclusion

This project establishes a Python-based pipeline for transforming daily 24-hour weather report PDFs into a structured and tidy dataset.

The current implementation focuses on data acquisition, PDF extraction, cleaning, daily dataset generation, master dataset maintenance, and reproducibility.

Further development will focus on strengthening the package structure, automated testing, scheduled execution, and continuous data collection.
