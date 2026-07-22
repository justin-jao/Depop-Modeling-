"""
str_calculator.py

Calculates eBay Sell-Through Rate (STR) for a search query:

    STR = (Sold Items / Total Items) * 100

Total items: pulled via the eBay Developer API (Browse API's search
endpoint returns a "total" field for the whole result set, not just
the current page) - fully official, no scraping.

Sold items: eBay does not expose this through any publicly-accessible
API. The old Finding API supported it but was decommissioned in Feb
2025; the Browse API has no sold/completed filter; the Marketplace
Insights API technically covers it but is a gated "Limited Release"
most developer accounts can't get approved for. So this half uses
Playwright to read the same "X results" count a person would see
browsing eBay's sold-listings search page themselves
(?LH_Sold=1&LH_Complete=1).

Setup:
    pip install requests python-dotenv playwright
    playwright install chromium
    cp .env.example .env   # fill in EBAY_CLIENT_ID / EBAY_CLIENT_SECRET

Run:
    python str_calculator.py
"""

import base64
import os
import re
import urllib.parse

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EBAY_ENV = os.environ.get("EBAY_ENV", "PRODUCTION").upper()  # PRODUCTION or SANDBOX
CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

if EBAY_ENV == "SANDBOX":
    OAUTH_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.sandbox.ebay.com/buy/browse/v1"
else:
    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"


def get_app_token() -> str:
    """OAuth client-credentials flow against eBay's Developer API."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set. "
            "Copy .env.example to .env and fill in your keys."
        )

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        OAUTH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"eBay OAuth failed ({resp.status_code}): {resp.text}")

    return resp.json()["access_token"]


def get_total_active_count(token: str, query: str) -> int:
    """Total number of currently active listings matching the query -
    via the official Browse API's 'total' field. limit=1 because we
    only need the count, not the items themselves."""
    resp = requests.get(
        f"{BROWSE_BASE}/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        },
        params={"q": query, "limit": 1},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("total", 0)


# Matches things like "1,234 results" or "18,000+ results" in the page text.
RESULT_COUNT_RE = re.compile(r"([\d,]+)\+?\s*results?", re.IGNORECASE)


def get_sold_count(query: str) -> int:
    """Number of sold listings matching the query (eBay's sold/completed
    window, typically the last ~90 days). No public API exposes this,
    so this reads the same results-count heading a person would see
    browsing eBay's sold-listings search page themselves."""
    search_url = (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={urllib.parse.quote_plus(query)}&LH_Sold=1&LH_Complete=1"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(search_url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("text=/results?/i", timeout=10000)
        except Exception:
            pass  # fall through - try to parse whatever loaded anyway

        page_text = page.inner_text("body")
        browser.close()

    match = RESULT_COUNT_RE.search(page_text)
    if not match:
        raise RuntimeError(
            "Couldn't find a results count on eBay's sold-listings page. "
            "Either eBay changed their page layout, or this query genuinely "
            "has zero sold results."
        )
    return int(match.group(1).replace(",", ""))


def calculate_str(query: str):
    print(f"Getting OAuth token ({EBAY_ENV})...")
    token = get_app_token()

    print(f"Fetching total active listings for: {query}")
    total = get_total_active_count(token, query)
    print(f"  Total active listings: {total}")

    print(f"Fetching sold listings for: {query} (via Playwright)")
    sold = get_sold_count(query)
    print(f"  Sold listings: {sold}")

    if total == 0:
        print("No active listings found - can't calculate a sell-through rate.")
        return None

    # This single multiplication by 100 is what turns the ratio into a
    # percentage - nothing downstream should multiply by 100 again.
    str_percent = (sold / total) * 100

    print(f"\nSell-Through Rate for '{query}': {str_percent:.2f}%")
    return str_percent


if __name__ == "__main__":
    user_query = input("Enter your eBay search query: ")
    calculate_str(user_query)
