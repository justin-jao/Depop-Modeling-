# Poshmark Scraper

Scrapes Poshmark search results and writes one JSON file per listing plus one JSON file per unique seller.

## Setup

**Fastest option**

From this folder, run:

```bash
./run.sh
```

The launcher will:
- create `venv/` if needed
- install Playwright into that environment
- install Chromium for Playwright
- run the scraper

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
   pip install playwright
   playwright install chromium
   ```

3. Run the scraper:

   ```bash
   python poshmark-scraper
   ```

## Output

The scraper writes:
- `poshmark_results/` — one JSON file per listing
- `poshmark_sellers/` — one JSON file per unique seller

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
