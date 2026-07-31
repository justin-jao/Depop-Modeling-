# Poshmark Scraper

Scrapes Poshmark search results and writes one JSON file per listing plus one JSON file per unique seller.

## Setup

The scraper is self-bootstrapping. Anyone with Python 3.9+ can run it directly.

From the repository root:

```bash
python poshmark/poshmark-scraper --query "nike"
```

Optional flags:
- `--limit 5` to process fewer listing URLs for a faster run
- Omit `--query` to be prompted interactively

**Manual option**

1. Create and activate a virtual environment:

   **macOS / Linux**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   **Windows (PowerShell)**
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

2. Install Playwright:

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. Run the scraper:

   ```bash
   python poshmark-scraper --query "nike"
   ```

## Output

The scraper writes:
- `storage/poshmark/results/` — one JSON file per listing
- `storage/poshmark/sellers/` — one JSON file per unique seller
- `storage/poshmark/scrape_runs.jsonl` — loading-zone run metadata
- `storage/poshmark/raw_listings.jsonl` — loading-zone raw payload rows

Listing files include the parsed item data and seller fields. Seller files use the shared shape:

```json
{
  "source": "poshmark",
  "seller_id": "...",
  "username": "...",
  "rating": null,
  "items_sold": 123
}
```

Poshmark does not expose a seller rating in this scraper, so `rating` is always `null`.

## Notes

- The scraper is best-effort and uses the current listing page, bootstrap state, and closet pages to extract data.
- If Poshmark changes its page structure, check the raw listing output first and then adjust the extraction helpers in `poshmark-scraper`.
