# eBay Listing Fetcher (script only)

Pulls listings from eBay's Browse API using your Developer keyset and
writes them to a raw JSON file. No server, no frontend.

## Setup

**Easiest way — one command, no manual installs:**

Mac/Linux:
```bash
chmod +x run.sh
./run.sh
```

Windows: double-click `run.bat` (or run it from Command Prompt).

First run will create a local `venv/` folder, install the two
dependencies into it, and generate a `.env` file for you to fill in —
then it'll stop and ask you to add your eBay keys. Run it again after
that and it goes straight to scraping. Every run after that reuses the
same `venv/`, so nothing gets reinstalled unless you delete it.

**Manual way, if you prefer:**
```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your eBay Developer keyset:
```
EBAY_CLIENT_ID=your-client-id
EBAY_CLIENT_SECRET=your-client-secret
EBAY_ENV=PRODUCTION
EBAY_MARKETPLACE_ID=EBAY_US
```

## Run

If you used `run.sh` / `run.bat` above, it already ran the script for
you. To run it again later:

```bash
./run.sh        # Mac/Linux
run.bat         # Windows
```

Or manually, if you set things up yourself:
```bash
python ebay_scrape.py
```

It will prompt you for a search query, then write **one JSON file per
listing** into an `ebay_results/` folder (created automatically),
named after each item's ID — e.g. `ebay_results/176212861437.json`.

Pulls 10 listings per query by default.

## Output shape

Each file in `ebay_results/` looks like:

```json
{
  "item_id": "176212861437",
  "name": "...",
  "condition": "...",
  "size": "...",
  "brand": "...",
  "price": "45.00 USD",
  "price_note": null,
  "description": "...",
  "creation_time": "2026-03-14T10:22:00.000Z",
  "seller_name": "...",
  "category": "...",
  "location": "...",
  "url": "https://www.ebay.com/itm/..."
}
```

Adjust `RESULTS_LIMIT` near the top of `ebay_scrape.py` to pull more
or fewer listings per search (default 10).