# Poshmark ELT Scraper

Extracts raw listing payloads from Poshmark and writes them in the same
landing-zone format used by the Depop pipeline.

## Data Pipeline Role

1. **Extract (`poshmark/poshmark-scraper`)**
   Crawls Poshmark search results, opens listing pages, intercepts JSON API
   responses, and keeps the best listing-relevant payload.
2. **Load (shared `pipeline.load.py`)**
   Reads JSON files from `storage/datasets/default` and inserts them into
   `raw_listings`.
3. **Transform (shared `pipeline.transform.py`)**
   Converts raw payloads into normalized tables.

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
pip install -r poshmark/requirements.txt
playwright install chromium
```

### 3. Run the scraper

```bash
python poshmark/poshmark-scraper --query "nike"
```

Optional flags:
- `--max-items 5`
- omit `--query` to type your query interactively

## Output Shape

Writes one record per scraped listing under:
- `storage/datasets/default/*.json`

Each record matches the Depop raw contract:

```json
{
  "source_url": "https://poshmark.com/listing/...",
  "api_payload": { "...": "raw intercepted JSON ..." }
}
```

## Notes

- Interception quality depends on Poshmark network behavior.
- If payload capture drops, tune the URL/content filters in
  `poshmark/poshmark-scraper`.
