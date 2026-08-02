# eBay ELT Scraper

Extracts raw listing payloads from eBay Browse API and writes them in the same
landing-zone format used by the Depop pipeline.

## Data Pipeline Role

1. **Extract (`ebay/ebay_scrape.py`)**
   Calls eBay Browse API endpoints, filters Buy It Now listings, and writes
   raw summary/detail payloads.
2. **Load (shared `pipeline.load.py`)**
   Reads JSON files from `storage/datasets/default` into `raw_listings`.
3. **Transform (shared `pipeline.transform.py`)**
   Converts raw payloads into normalized records.

## Getting Started

### 1. Create a virtual environment

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r ebay/requirements.txt
```

### 3. Configure eBay credentials

Create `ebay/.env` with:

```env
EBAY_CLIENT_ID=your-client-id
EBAY_CLIENT_SECRET=your-client-secret
EBAY_ENV=PRODUCTION
EBAY_MARKETPLACE_ID=EBAY_US
```

### 4. Run the scraper

```bash
python ebay/ebay_scrape.py --query "nike"
```

Optional flags:
- `--limit 5`
- omit `--query` to type your query interactively

## Output Shape

Writes one record per scraped listing under:
- `storage/datasets/default/*.json`

Each record matches the Depop raw contract:

```json
{
  "source_url": "https://www.ebay.com/itm/...",
  "api_payload": {
    "item_summary": { "...": "raw eBay summary JSON ..." },
    "item_detail": { "...": "raw eBay detail JSON ..." }
  }
}
```