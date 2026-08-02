# Vinted ELT Scraper

Extracts raw item payloads from Vinted and writes them in the same landing-zone
format used by the Depop pipeline.

## Data Pipeline Role

1. **Extract (`vinted/vinted_scraper.py`)**
   Crawls Vinted search results, opens item pages, intercepts JSON API
   responses, and stores the best candidate payload.
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
pip install -r vinted/requirements.txt
playwright install chromium
```

### 3. Run the scraper

```bash
python vinted/vinted_scraper.py --query "nike"
```

Optional flags:
- `--max-items 5`
- `--domain vinted.co.uk`
- omit `--query` to type your query interactively

## Output Shape

Writes one record per scraped item under:
- `storage/datasets/default/*.json`

Each record matches the Depop raw contract:

```json
{
  "source_url": "https://www.vinted.co.uk/items/...",
  "api_payload": { "...": "raw intercepted JSON ..." }
}
```

## Notes

- Vinted uses anti-bot protection (Datadome), which may reduce capture rate.
- If payload capture drops, adjust URL/content filters and scoring in
  `vinted/vinted_scraper.py`.
