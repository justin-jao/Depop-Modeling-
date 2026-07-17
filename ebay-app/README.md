# eBay Listing Manifest

A small full-stack demo: a Flask backend that holds your eBay app
credentials and talks to eBay's Browse API, plus a single-page
frontend that only ever talks to *your* backend.

```
ebay-app/
  backend/
    app.py            Flask routes: /api/listings, /api/health, serves frontend
    ebay_client.py     OAuth token exchange + Browse API calls
    cache_db.py         SQLite cache so repeat searches don't re-hit eBay
    requirements.txt
    .env.example
  frontend/
    index.html          Search box + results, calls /api/listings only
```

## How the pieces fit together

**Keyword search:**
1. Browser loads `index.html`, user searches for something.
2. Frontend calls **your backend**: `GET /api/listings?q=...`
3. Backend checks `cache_db.py` — any item fetched in the last 6 hours
   is served straight from SQLite, no eBay call.
4. For anything not cached, `ebay_client.py`:
   - Gets (or reuses) an Application access token via OAuth
     client-credentials — this token is shared across *all* visitors,
     since it belongs to your app, not to any individual user.
   - Calls `item_summary/search` to find matching items.
   - Calls `item/{id}` for each result to get full details, including
     `itemCreationDate` (the real listing-creation timestamp).
5. Backend maps the raw response down to the 8 fields you asked for
   and returns clean JSON. Frontend never sees eBay's raw payload or
   your credentials.

**Single-URL lookup:**
1. Frontend calls `GET /api/listing?url=<full ebay.com/itm/... URL>`.
2. Backend extracts the numeric legacy item ID from the URL with a
   regex (handles `/itm/1234567890`, `/itm/Some-Title/1234567890`,
   and either with tracking query params attached).
3. Same cache-then-`get_item_by_legacy_id` flow as above, but for one
   item instead of a search's worth of results.
4. Returns the same 8-field shape as the search endpoint, so the
   frontend reuses one render function for both modes.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edit .env with your eBay Developer keyset (start with SANDBOX)
python app.py
```

Then open `http://localhost:5000` — the Flask app serves the frontend
directly, so there's nothing separate to run.

## Getting eBay credentials

1. Create a free account at the eBay Developer Program site.
2. Create an application keyset (Sandbox first).
3. Sandbox lets you test the whole flow against fake data with no
   approval wait. When you're ready to show real listings, apply for
   Production access from the same dashboard — that application goes
   through eBay's eligibility review before they issue a Production
   keyset.
4. Put the keyset's Client ID / Client Secret into `.env`. Never commit
   `.env` or put these values in any frontend code.

## About the shared rate limit

Every visitor's search draws from the same daily call quota, because
they're all funneled through your one backend token. The SQLite cache
is what keeps that sustainable — popular searches get served from
cache instead of re-querying eBay. If you outgrow eBay's default
limits, you request a higher allowance via eBay's Application Growth
Check in the developer dashboard rather than provisioning per-user
credentials.

## Notes / things to harden before going live

- Swap SQLite for Postgres/Redis if you expect concurrent write load.
- Add basic rate limiting on `/api/listings` itself (e.g. Flask-Limiter)
  so one abusive visitor can't burn your whole eBay quota alone.
- `itemCreationDate` and `description` are the two fields most worth
  double-checking per category — some listing types omit them.
