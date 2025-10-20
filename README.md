
<p align="center">
  <img src="app/assets/daphnia.svg" alt="Daphnia" width="200" />
</p>

<h1 align="center">Daphnia Analysis</h1>


<p align="center">
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  </a>
  <a href="https://streamlit.io/">
    <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white">
  </a>
  <a href="https://pandas.pydata.org/">
    <img alt="pandas" src="https://img.shields.io/badge/pandas-Data-150458?logo=pandas&logoColor=white">
  </a>
  <a href="https://docs.sqlalchemy.org/">
    <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00">
  </a>
</p>

<p align="center">
  <a href="https://www.postgresql.org/">
    <img alt="PostgreSQL (Neon)" src="https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white">
  </a>
  <a href="https://developers.google.com/sheets/api">
    <img alt="Google Sheets" src="https://img.shields.io/badge/Google%20Sheets-ETL-34A853?logo=googlesheets&logoColor=white">
  </a>
  <a href="https://github.com/features/actions">
    <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-Scheduler-2088FF?logo=githubactions&logoColor=white">
  </a>
</p>

> **🌐 해외 사용자 안내:** 이 저장소는 팀 요구에 따라 **주로 영어로 문서화**되어 있으며, **이슈·커밋 메시지·코드 주석·위키 문서** 모두 영어로 작성됩니다. 원활한 이해를 위해 브라우저의 페이지 번역 기능을 사용해 주세요.  
> (Chrome: 우측 상단 **⋮ (더보기) → 번역** 또는 주소창의 번역 아이콘 | Firefox/Safari: 유사한 옵션 제공)

## 🔗 Table of Contents

- [📍 Overview](#-overview)
- [✨ Key Features](#-key-features)
- [🏗️ Architecture](#️-architecture)
- [📁 Project Structure](#-project-structure)
- [🚀 Getting Started](#-getting-started)
  - [☑️ Prerequisites](#-prerequisites)
  - [⚙️ Installation](#-installation)
  - [🤖 Usage](#-usage)
- [📊 Application Features](#-application-features)
- [🔧 Development](#-development)
- [📌 Project Status](#-project-status)
- [🎗 License](#-license)
- [🙌 Acknowledgments](#-acknowledgments)

---

## 📍 Overview

**Daphnia Coding Protocol** is an intelligent ID generation and management system designed for Daphnia (water flea) research laboratories. The platform automates the complex process of generating offspring IDs, managing generational tracking, and making data-driven decisions about specimen viability. Built with Streamlit for an intuitive web interface, it integrates with PostgreSQL databases and Google Sheets to provide real-time research data management.

### Core Purpose
- **Intelligent ID Generation**: Automatically generates standardized offspring IDs based on parent lineage and date
- **Discard Decision Support**: AI-powered recommendations on whether to keep or discard specimens based on generation limits and population thresholds
- **Data Normalization**: Accepts varied ID formats, normalizing them to a standardized dotted notation
- **Real-time Synchronization**: Automated ETL pipelines sync data from Google Sheets to PostgreSQL via GitHub Actions
- **Research Analytics**: Comprehensive visualization and analysis tools for tracking Daphnia populations and breeding patterns

---

## ✨ Key Features

### Intelligent ID Generation
- **Parent-Based Generation**: Automatically creates child IDs based on parent lineage (e.g., `E.1` → `E.1.1`, `E.1.2`)
- **Date Suffix Automation**: Appends date suffixes in `_MMDD` format (e.g., `E.1.1_0804`)
- **Smart Defaults**: Uses today's date (KST timezone) when no date is specified
- **Sibling Tracking**: Automatically increments child indices to avoid ID conflicts

### Flexible Input Normalization
- **Mixed Format Support**: Accepts formats like `E1`, `E.01`, `E1.2` and normalizes to `E.1`, `E.1.2`
- **Case Insensitive**: Handles both uppercase and lowercase inputs (`e1` → `E.1`)
- **Full ID Parsing**: Extracts core IDs from full IDs with date suffixes (`E.1_0804` → core `E.1`)
- **Latest Record Lookup**: When given core-only input, finds the most recent record by date suffix

### Automated Data Pipeline
- **GitHub Actions Scheduling**: Daily automated data refresh at midnight KST
- **Google Sheets Integration**: Seamless ETL from research spreadsheets to PostgreSQL
- **Multi-Table Management**: Syncs `records`, `broods`, and `current` tables
- **Error Handling**: Robust error logging and recovery mechanisms

### Research Analytics
- **Population Visualizations**: Track specimen counts, generation distributions, and breeding patterns
- **Lineage Exploration**: View parent details and all existing children for context
- **Status Monitoring**: Real-time tracking of alive/dead specimens
- **Data Export**: Easy export of analysis results for further research

---

## 🏗️ Architecture

![Daphnia-Architecture](app/assets/daphnia_analysis_architecture.png)

### Architecture Overview

The Streamlit app is deployed read-only against a Neon Postgres database. A daily GitHub Actions workflow (00:00 KST) uses a Google Service Account to read Google Sheets, preprocess data, and upsert into Neon. The app reads from Neon with st.cache_data (TTL ~24h) for fast dashboards. The same GitHub repository contains both the Streamlit UI code and the ETL code; only Actions performs database writes.

### Data Flow

- GitHub Actions (daily) loads Google Service Account creds from secrets. 
- Read Google Sheets → preprocess → upsert/merge (RW) into Neon. 
- Streamlit app issues read-only SQL to Neon; responses are cached (TTL). 

Users interact with the UI; no writes originate from the app.

---

## 📁 Project Structure

```sh
daphnia-coding-protocol/
├── 📱 app/                           # Main Application
│   ├── 🎨 assets/                    # Static Assets
│   │   ├── daphnia.svg              # App Logo
│   │   └── marine_ugent.png         # General Logo
│   │
│   ├── 🧠 core/                      # Core Business Logic
│   │   ├── coder.py                 # ID Generation Engine
│   │   ├── database.py              # PostgreSQL Connection & Queries
│   │   ├── utils.py                 # Helper Functions
│   │   └── visualizations.py        # Data Visualization Components
│   │
│   ├── 🖼️ ui/                        # User Interface
│   │   ├── coder_page.py            # ID Generator Page
│   │   ├── analysis_page.py         # Analytics Dashboard
│   │   └── test_connectivity.py     # Database Health Check
│   │
│   ├── ⚙️ .streamlit/                # Streamlit Configuration
│   │   └── config.toml              # App Settings
│   │
│   └── 🚀 main.py                    # Application Entry Point
│
├── 🔄 etl/                           # ETL Pipeline
│   ├── refresh_records.py           # Sync Records Table
│   ├── refresh_broods.py            # Sync Broods Table
│   └── refresh_current.py           # Sync Current Table
│
├── 📊 data/                          # Local Data Cache
│
├── 🔧 scripts/                       # Utility Scripts
│   ├── db_check.py                  # Database Verification
│   └── test_current_table.py        # Table Testing
│
├── 🤖 .github/                       # CI/CD Configuration
│   └── workflows/                   # GitHub Actions
│       └── daily_refresh.yml        # Scheduled ETL Jobs
│
├── 📋 requirements.txt               # Python Dependencies
├── 📄 README.md                      # Documentation
└── 🎗 LICENSE.md                     # MIT License
```

---

## 🚀 Getting Started

### ☑️ Prerequisites

- **Python 3.12+** and pip package manager
- **PostgreSQL Database** (Neon or local instance)
- **Google Cloud Service Account** with Google Sheets API access
- **Streamlit Account** (for cloud deployment, optional)
- **GitHub Account** (for automated ETL scheduling)

### ⚙️ Installation

#### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/chaerheeon/daphnia-coding-protocol.git
cd daphnia-coding-protocol

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Set up Streamlit secrets (app/.streamlit/secrets.toml)
# Add the following variables:
# DAPHNIA_DATABASE_URL = "postgresql://user:password@host:port/database?sslmode=require"
# GOOGLE_SERVICE_ACCOUNT_JSON = '''{ ... service account JSON ... }'''
# DAPHNIA_GOOGLE_SHEET_ID = "your_google_sheet_id"
```

#### GitHub Secrets Setup (for automated ETL)

Configure the following secrets in your GitHub repository settings:

1. **`DATABASE_URL`**: PostgreSQL connection string (Neon)
   ```
   postgresql://user:password@host:port/database?sslmode=require
   ```

2. **`GOOGLE_SERVICE_ACCOUNT_JSON`**: Full JSON content of your Google Cloud service account key
   ```json
   {
     "type": "service_account",
     "project_id": "your-project-id",
     ...
   }
   ```

3. **`GOOGLE_SHEET_ID`**: The ID of your Google Sheet (from the URL)
   ```
   https://docs.google.com/spreadsheets/d/[THIS_IS_THE_ID]/edit
   ```

#### Streamlit Cloud Secrets Setup

In your Streamlit Cloud dashboard, add these secrets in TOML format:

```toml
DAPHNIA_DATABASE_URL = "postgresql://user:password@host:port/database?sslmode=require"

GOOGLE_SERVICE_ACCOUNT_JSON = '''
{
  "type": "service_account",
  "project_id": "your-project-id",
  ...
}
'''

DAPHNIA_GOOGLE_SHEET_ID = "your_google_sheet_id"
```

### 🤖 Usage

#### Running Locally

```bash
# Start Streamlit app
streamlit run app/main.py

# App will open at http://localhost:8501
```

#### Cloud Deployment

```bash
# Deploy to Streamlit Cloud
# 1. Push to GitHub
# 2. Connect repository on streamlit.io
# 3. Set secrets in Streamlit Cloud dashboard
# 4. Deploy!

# Live app: https://daphnia-coding-protocol.streamlit.app/
```

---

## 📊 Application Features

<details>
  <summary><strong>Page 1: Daphnia Code Generator</strong></summary>

**Purpose**: Intelligently generate offspring IDs and make discard decisions based on parent lineage and lab protocols.

#### How to Use
1. **Open the App**: Visit <a href="https://daphnia-coding-protocol.streamlit.app/">daphnia-coding-protocol.streamlit.app</a>
2. **Check Data Freshness**: Look for "Last refresh (KST)" under the subtitle  
   - Ensure it shows today's date  
   - Data modified after 12:00 AM KST won't be reflected until next refresh  
   - If stale, notify supervisor to trigger manual refresh
3. **Enter Mother ID**: Input in the first text box  
   - **Core only**: `E.1`, `E.1.3`, `A.2`, `B.3`  
   - **Full ID with date**: `E.1_0804`, `E.1.3_0912`
4. **Date Suffix**: Automatically defaults to today's date in `_MMDD` format (KST timezone)  
   - Manually change if generating IDs for past/future dates  
   - Leave blank to use today's date automatically
5. **Review Results**:
   - **Matched Parent**: Shows the resolved full ID and normalized core
   - **Set & Assignee**: Displays set label and assigned researcher
   - **Suggested Child ID**: Complete ID with date suffix (e.g., `E.1.1_0804`)
   - **Discard Recommendation**:
     - 🔴 **Red "Discard? Yes"**: Specimen should be discarded (with reason)
     - ⬜ **"Discard? No"**: Specimen is viable for continuation
     - 💡 **Info Note**: For 3rd broods, shows "optimal for experimental use"
   - **Reasoning**: Clear explanation of the decision logic
6. **Expand Details** (optional):
   - **Parent Details**: Full JSON of parent brood record
   - **Existing Children**: List of all offspring IDs from this parent

#### Input Normalization Examples

The system accepts mixed formats and normalizes them automatically:

| You Type | Interpreted Core | Normalization Applied |
|----------|------------------|----------------------|
| `E1` / `e1` / `E.01` | `E.1` | Uppercase letter, single-digit generation |
| `E1.2` / `E.1.02` | `E.1.2` | Dotted notation with normalized numbers |
| `E.1_0804` | `E.1` (date: `_0804`) | Core extracted, date preserved |
| `A2` / `A.2` | `A.2` | Set A standard format |
| `B3.1_0912` | `B.3.1` (date: `_0912`) | Set B with hierarchy and date |

**Core ID Format**: `LETTER.GENERATION.HIERARCHY` (e.g., `E.2.3` = Set E, Generation 2, 3rd offspring)  
**Full ID Format**: `CORE_MMDD` (e.g., `E.2.3_0804` = born on August 4th)

#### Discard Decision Logic

1. **Generation Limit Exceeded**:
   - Triggers when parent generation ≥ 3 (Gen 4+ offspring would be created)
   - Reason: *"Mother has reached generation limit (Gen X)"*
   - Applies to all sets (E, A, B)

2. **Population Threshold Exceeded**:
   - **Set E**: > 100 alive specimens
   - **Sets A & B**: > 50 alive specimens
   - Reason: *"Set X population exceeds threshold (N alive)"*
   - Counts only broods with no death_date and status ≠ dead

3. **Mother Deceased**:
   - Mother has `death_date` filled OR `status` = "dead"
   - Reason: *"Mother is no longer alive"*
   - Shows prominent warning: ⚠️ **WARNING: This mother is DEAD**

4. **Experimental Optimization Note**:
   - 3rd broods trigger info message: *"Third broods are optimal for experimental use"*

</details>

<details>
  <summary><strong>Page 2: Daphnia Analysis</strong></summary>

**Purpose**: Comprehensive analytics dashboard for monitoring Daphnia populations, mortality trends, and environmental factors.

#### Features

**🔝 Top-Level Tabs**:
- **🌍 Cumulative Tab**: Aggregated data across all sets (E, A, B)
- **🧬 Individual Set Tabs**: Separate analysis for each set with assigned researcher info

**📊 KPI Metrics** (displayed as cards):
- **Total Records**: Count of all observation records in the dataset
- **Unique Mothers**: Number of distinct mother IDs
- **Alive Broods**: Current number of active broods (no death_date)
- **Avg Brood Life Expectancy**: Mean lifespan in days (for deceased broods only)

**👥 Current Population by Life Stage**:
> **Data Source**: The `current` table (materialized view) contains the most recent record for each alive brood. This table is refreshed daily by the ETL pipeline (`refresh_current.py`), which:
> 1. Queries `broods` table for alive mothers (no death_date, status ≠ dead)
> 2. Joins with `records` table to get the latest record by date
> 3. Stores in `current` table with life_stage and other current state info

- **🟢 Adults**: Sum of `n_i` for "adult" stage broods
- **🟡 Adolescents**: Sum of `n_i` for "adolescent"/"adolescence" stage broods
- **🔵 Neonates**: Sum of `n_i` for "neonate" stage broods
- **👥 Total**: Sum of all `n_i` values for alive broods

**📈 Visualizations**:
1. **Life Expectancy Distribution (Dead Broods)**
   - Histogram showing distribution of lifespan in days
   - Includes mean and max life expectancy metrics
2. **Additional Charts** (dynamically generated from chart definitions)
   - Mortality trends over time
   - Environmental factor analysis
   - Behavioral pattern tracking
   - Population growth curves

**🔍 Data Quality Panel** (collapsible):
- Shows records with missing dates
- Explains data completeness issues
- Lists affected mother IDs

**📋 Raw Data Preview**:
- Sortable table of all records in the selected tab
- Full column visibility for detailed inspection

#### Navigation
- Use top tabs to switch between cumulative and per-set views
- Each set tab shows **assigned researcher** name
- Charts automatically filter to the selected dataset

</details>

---

## 🔧 Development

### Project Philosophy

This system follows a **data-driven, rule-based approach** to research lab management:
- **Standardization**: All IDs follow strict dotted notation (e.g., `E.1.2.3`)
- **Automation**: Minimize manual data entry and human error
- **Transparency**: All discard decisions include clear reasoning
- **Flexibility**: Accept various input formats for ease of use
- **Reliability**: Automated daily syncs ensure data freshness (12 AM KST)

### Code Organization

- **`app/core/coder.py`**: Core ID generation and discard logic algorithms
- **`app/core/database.py`**: SQLAlchemy queries, data caching, and connection management
- **`app/core/utils.py`**: Helper functions for date parsing, formatting, and data preparation
- **`app/core/visualizations.py`**: Altair chart definitions and data visualization builders
- **`app/ui/coder_page.py`**: Streamlit UI for the Code Generator page
- **`app/ui/analysis_page.py`**: Streamlit UI for the Analysis Dashboard page
- **`etl/refresh_broods.py`**: Syncs `broods` table from Google Sheets
- **`etl/refresh_records.py`**: Syncs `records` table from Google Sheets
- **`etl/refresh_current.py`**: Materializes `current` table (alive broods with latest record)
- **`scripts/`**: Testing and database verification utilities

### ETL Pipeline Details

**Automated Schedule**: Daily at 12:00 AM KST (15:00 UTC) via GitHub Actions

**Pipeline Flow**:
1. **`refresh_broods.py`**:
   - Reads all Google Sheets tabs matching pattern `^set [a-z]`
   - Extracts set label and assigned person from tab titles
   - Normalizes mother_id format to canonical dotted notation
   - Computes SHA-256 hash of all rows for change detection
   - Updates PostgreSQL `broods` table only if changes detected
   - Stores metadata (row count, last refresh timestamp, schema name)
2. **`refresh_records.py`**:
   - Reads observation records from Google Sheets
   - Joins with broods to add set_label and assigned_person
   - Validates and normalizes mother_id references
   - Uses hash-based change detection (only updates on actual changes)
   - Populates `records` table with timestamped observations
3. **`refresh_current.py`**:
   - Queries `broods` WHERE death_date IS NULL AND status != 'dead'
   - LEFT JOINs with `records` to get latest record per mother_id
   - Materializes result into `current` table
   - Used by Analysis page for real-time population metrics

**Environment Variables** (GitHub Secrets):
- `DATABASE_URL`: PostgreSQL connection string (Neon serverless)
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Service account credentials JSON
- `GOOGLE_SHEET_ID`: Google Sheets document ID

### Running Tests

```bash
# Test database connectivity and table schemas
python scripts/db_check.py

# Test current table materialization
python scripts/test_current_table.py

# Manual ETL execution (local testing)
export DATABASE_URL="postgresql://..."
export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }'
export GOOGLE_SHEET_ID="your_sheet_id"

python etl/refresh_broods.py
python etl/refresh_records.py
python etl/refresh_current.py
```
---

## 📌 Project Status

### ✅ Current Features
- [x] **Intelligent ID Generation**: Parent-based offspring ID creation with date suffixes
- [x] **Input Normalization**: Accepts and standardizes mixed formats
- [x] **Discard Logic**: Generation limits, population thresholds, and viability checks
- [x] **Real-time Data Sync**: Automated daily ETL from Google Sheets to PostgreSQL
- [x] **Web Interface**: Streamlit-based user-friendly application
- [x] **Analytics Dashboard**: Population visualizations and lineage tracking
- [x] **GitHub Actions**: Automated scheduling and deployment
- [x] **Error Handling**: Robust validation and error recovery

### 🚀 Future Enhancements
- [ ] Better Demographics
- [ ] Predictions of Neonate Generation
---

## 🎗 License

This project is licensed under the **MIT License** - see the [LICENSE.md](LICENSE.md) file for details.

**Copyright (c) 2025 UGent Korea**

---
## 🙌 Acknowledgments

### Institution
- **UGent Korea (Ghent University Global Campus)**: Research facility and institutional support
- **BEST Labs**: Affiliate Laboratory providing domain expertise and research guidance

### Credits

<div align="center">

| <a href="https://github.com/chaerheeon"><img src="https://github.com/chaerheeon.png?size=120" width="88" height="88" style="border-radius:50%"/></a> | <a href="https://github.com/chaerheeon"><img src="https://github.com/chaerheeon.png?size=120" width="88" height="88" style="border-radius:50%"/></a> |
|---|----------------------------------------------------------------------------------------------------------------------------------------------|
| **Creator**<br/><sub>Original author</sub> | **Maintainer**<br/>                                                                                                            |

</div>

---

<p align="center"><img src="app/assets/Best_Labs.png" alt="BEST Labs" width="140"/></p>

