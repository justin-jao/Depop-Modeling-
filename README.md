 # Depop ELT Scraper & Data Pipeline

An end-to-end Extract, Load, and Transform (ELT) pipeline for scraping Depop listings and sellers using **Crawlee**, **Playwright**, and **SQLite**.

##  Data Pipeline
This project follows an ELT workflow to preserve data lineage:
0. Setup DB (setup_db): use to setup SQlite database. 
1. **Extract (`depop.scrape.py`):** A headless Playwright crawler that navigates Depop search results and product pages, bypassing anti-bot protections using window positioning and stealth scripts.
2. **Load (`pipeline.load.py`):** Loads raw JSON payloads from Crawlee storage into an immutable landing zone (`raw_listings` table) inside SQLite.
3. **Transform (`pipeline.transform.py`):** Parses nested JSON, normalizes data into relational tables (`sellers` and `listings`), cleans prices, and handles deduplication via `UPSERT`.
TODO: need to fix sellers table, currently no items sold or rating. 

## Testing files
clean_db.py to wipe the JSON files and/or destroy the database
TODO: Need to make it so I can access key_value_stores and request_queues

testing.py to test the data pipeline. 
    test_pipeline_data(): goes through entire pipeline and checks tables
    clear_all_rows(): deletes all records in database
    reset_transform_stage(): deletes records in listing/seller table 

## API Gateway
Using FastAPI. currently set up in main.py.
http://127.0.0.1:8000/docs
Go here to test get/post requests, local server setup in web browser. 

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

###ELT Pipeline
python setup_db.py
python depop.scrape.py
python pipeline.load.py
python pipeline.transform.py
python testing.py

### fastAPI server
#--reload is so the server will automatically restart every time you save changes to the file
uvicorn main:app --reload 