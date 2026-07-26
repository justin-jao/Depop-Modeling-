 # Depop ELT Scraper & Data Pipeline

An end-to-end Extract, Load, and Transform (ELT) pipeline for scraping Depop listings and sellers using **Crawlee**, **Playwright**, and **SQLite**.

##  Architecture
This project follows an ELT workflow to preserve data lineage:
1. **Extract (`main.py`):** A headless Playwright crawler that navigates Depop search results and product pages, bypassing anti-bot protections using window positioning and stealth scripts.
2. **Load (`load.py`):** Loads raw JSON payloads from Crawlee storage into an immutable landing zone (`raw_listings` table) inside SQLite.
3. **Transform (`transform.py`):** Parses nested JSON, normalizes data into relational tables (`sellers` and `listings`), cleans prices, and handles deduplication via `UPSERT`.

##  Getting Started

### Clone the repository
```bash
git clone [https://github.com/justin-jao/Depop-Modeling-.git](https://github.com/justin-jao/Depop-Modeling-.git)
cd Depop-Modeling-

### Setting up virtual enviornment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

### Installing dependencies
pip install -r requirements.txt
playwright install chromium

###
# Initialize the SQLite database schema
python setup_db.py

# Scrape Depop (Extract)
python main.py

# Load raw JSON into the database landing zone (Load)
python load.py

# Normalize and clean the data into relational tables (Transform)
python transform.py

# Verify database health and view sample data
python testing.py