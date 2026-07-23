# Copilot instructions

## Setup and commands

This repository contains standalone scripts, not an installable Python package. Run commands from the directory indicated because output paths and `.env` discovery depend on the working directory.

### eBay sell-through-rate calculator (repository root)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
python str_calculator.py
```

`./run_str.sh` performs the same setup and run flow on macOS/Linux. The script requires `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`; `EBAY_ENV` defaults to `PRODUCTION`, and `EBAY_MARKETPLACE_ID` defaults to `EBAY_US`.

### eBay listing fetcher

Run this from the repository root so the root `.env` is loaded and results are written to the existing root `ebay_results/` directory:

```bash
source venv/bin/activate
python ebay-scraper-only/ebay_scrape.py
```

The root requirements already contain this script's `requests` and `python-dotenv` dependencies.

### Vinted scraper

Use a separate environment because Crawlee is only declared in the Vinted requirements:

```bash
cd vinted_scraper_only
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

There is currently no automated test suite, test runner, linter, formatter, or build step configured.

## Architecture

- `str_calculator.py` combines two data sources: the official eBay Browse API supplies the active-listing total, while synchronous Playwright parses the sold/completed results count from eBay's public search page. `calculate_str()` orchestrates OAuth, both counts, and the percentage calculation.
- `ebay-scraper-only/ebay_scrape.py` uses eBay's client-credentials OAuth flow, searches the Browse API, fetches full detail for each result, maps the response to a stable record, downloads the primary image as a base64 data URI, and writes one JSON file per listing.
- `vinted_scraper_only/main.py` uses an asynchronous Crawlee `PlaywrightCrawler`. It first establishes a browser session, calls Vinted's private catalog API through the page request context so cookies are shared, then visits each item page for best-effort enrichment from Next.js RSC flight chunks. It writes both Crawlee dataset data and one JSON file per listing under `vinted_scraper_only/results/`.
- The scripts do not share an internal library. The eBay OAuth/environment setup is duplicated between the two eBay entry points, while each scraper has its own record mapping and output schema.

## Repository-specific conventions

- Keep entry points interactive: each script prompts for a search query under `if __name__ == "__main__"`. Core work remains callable through `calculate_str(query)`, `run(query)`, or async `main()`.
- Search limits are module constants (`RESULTS_LIMIT` and `MAX_LISTINGS`), both currently `10`. Vinted's marketplace domain is intentionally fixed to `vinted.co.uk` in `main()`.
- Treat external response shapes defensively. eBay mapping uses optional dictionaries and `extract_aspect()`; Vinted uses `_get()`, fallbacks, and recursive flight-stream parsing. Do not turn missing optional marketplace fields into hard failures.
- Preserve source evidence when changing Vinted extraction. Records retain `raw_payload`, and the first item writes catalog, HTML, and parsed-flight debug artifacts so API or frontend shape changes can be diagnosed.
- Vinted's `status` field means item condition, not listing availability. `build_record()` derives availability from `closing_action`, `is_reserved`, and `is_visible`.
- Vinted enrichment is best-effort: catalog-summary records remain valid when item-page navigation or flight parsing fails. Catalog API failures, by contrast, are logged and stop that crawl.
- Generated data is UTF-8 JSON with indentation and `ensure_ascii=False`. The eBay fetcher embeds image bytes in `image_base64`; Vinted uses image URLs and retains the original payload.
- The checked-in Vinted README describes an older interception-based flow and domain prompt. Use `vinted_scraper_only/main.py` as the source of truth for current behavior and update the README when changing that flow.
