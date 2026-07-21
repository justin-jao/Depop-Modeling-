# Vinted Scraper (Crawlee + Playwright)

Scrapes up to 10 listings for a search query and saves them as JSON.

For each listing it captures:
- Listing ID
- User ID
- Brand ID
- Brand Name
- Listing status (on sale / reserved / closed)
- Category
- Seller description
- Last edited date
- Upload date
- Thumbnail image URL
- Item location (where it ships from)
- Condition
- Price (item price only, excluding shipping)

## How it works

Rather than scraping the rendered HTML, the script drives a real Chromium
browser (via Playwright) to the Vinted search page and to each listing page,
and **intercepts the JSON API calls that Vinted's own frontend makes** while
those pages load:

1. **Stage 1** loads the search results page and captures the response from
   Vinted's catalog/search API to get a list of listing IDs.
2. **Stage 2** visits each listing page and captures the response from the
   item-detail API, which has the full record (description, dates, brand,
   condition, etc).

This mirrors how Vinted's site works internally, so it's more resilient to
front-end HTML/CSS changes than a pure DOM scraper.

## Setup (VS Code)

1. Open this folder in VS Code.
2. Create and activate a virtual environment:

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

   In VS Code, once the venv exists you can also just pick it via
   `Ctrl+Shift+P` -> "Python: Select Interpreter" -> `./venv`.

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. Run it:
   ```bash
   python main.py
   ```

   You'll be prompted for:
   - A search query (e.g. `nike air max`)
   - A Vinted domain (e.g. `vinted.co.uk`, `vinted.de`, `vinted.fr` — Vinted
     runs per-country sites, so pick the one you want to search)

5. Output:
   - `vinted_results.json` in this folder — the 10 clean records.
   - `storage/` — Crawlee's own request queue/dataset (safe to delete/ignore).

## Notes & troubleshooting

- **Anti-bot protection**: Vinted uses Datadome. If a run comes back with 0
  results, set `headless=False` in `main.py` (in the `PlaywrightCrawler(...)`
  call) and re-run so you can see whether a challenge/CAPTCHA is blocking the
  browser, and solve it manually once.
- **Unofficial API**: Vinted's API isn't publicly documented, and field names
  can vary slightly by locale or change over time. `build_record()` in
  `main.py` pulls each field defensively with fallbacks, and every record
  also keeps the full `raw_payload` — if any extracted field comes back
  `None`, check `raw_payload` for the real key name and adjust `build_record`.
- **Rate limiting / ToS**: scraping Vinted may be against its Terms of
  Service. Use reasonable delays/volumes and at your own discretion/risk.
