import argparse
import base64
import json
import os
import re
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

EBAY_ENV = os.environ.get("EBAY_ENV", "PRODUCTION").upper()
CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

_EBAY_URLS = {
    "SANDBOX": (
        "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        "https://api.sandbox.ebay.com/buy/browse/v1",
    ),
    "PRODUCTION": (
        "https://api.ebay.com/identity/v1/oauth2/token",
        "https://api.ebay.com/buy/browse/v1",
    ),
}
OAUTH_URL, BROWSE_BASE = _EBAY_URLS.get(EBAY_ENV, _EBAY_URLS["PRODUCTION"])

DEFAULT_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
RESULTS_LIMIT = 20
SEARCH_PAGE_SIZE = 200
BUY_IT_NOW_FILTER = "buyingOptions:{FIXED_PRICE}"

PROJECT_DIR = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_DIR.parent / "storage" / "datasets" / "default"


def _normalized_oauth_scope() -> str:
    raw = os.environ.get("EBAY_SCOPE", DEFAULT_OAUTH_SCOPE)
    cleaned = raw.strip().strip('"').strip("'")
    scopes = [token for token in re.split(r"[\s,]+", cleaned) if token]
    return " ".join(scopes) if scopes else DEFAULT_OAUTH_SCOPE


OAUTH_SCOPE = _normalized_oauth_scope()


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
    }


def _write_dataset_record(record: dict) -> Path:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"ebay_{int(time.time() * 1000)}_{uuid.uuid4().hex}.json"
    out_path = DATASET_DIR / filename
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def is_buy_it_now_only(item_data: dict) -> bool:
    buying_options = set(item_data.get("buyingOptions") or [])
    return "FIXED_PRICE" in buying_options and "AUCTION" not in buying_options


def get_app_token() -> str:
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
            "scope": OAUTH_SCOPE,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"eBay OAuth failed ({resp.status_code}): {resp.text}")

    return resp.json()["access_token"]


def search_items(token: str, query: str, limit: int) -> list[dict]:
    summaries: list[dict] = []
    offset = 0

    while len(summaries) < limit:
        page_limit = min(SEARCH_PAGE_SIZE, limit)
        resp = requests.get(
            f"{BROWSE_BASE}/item_summary/search",
            headers=_auth_headers(token),
            params={
                "q": query,
                "limit": page_limit,
                "offset": offset,
                "filter": BUY_IT_NOW_FILTER,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        item_summaries = payload.get("itemSummaries", [])
        if not item_summaries:
            break

        for summary in item_summaries:
            if is_buy_it_now_only(summary):
                summaries.append(summary)
                if len(summaries) >= limit:
                    break

        offset += len(item_summaries)
        if offset >= payload.get("total", 0):
            break

    return summaries


def get_item_detail(token: str, item_id: str) -> dict:
    resp = requests.get(
        f"{BROWSE_BASE}/item/{item_id}",
        headers=_auth_headers(token),
        params={"fieldgroups": "ADDITIONAL_SELLER_DETAILS"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json() or {}


def run(query: str, limit: int) -> None:
    print(f"Getting OAuth token ({EBAY_ENV})...")
    token = get_app_token()

    print(f"Searching eBay for: {query}")
    summaries = search_items(token, query, limit)
    print(f"Found {len(summaries)} Buy It Now results, pulling full detail for each...")

    written = 0
    for idx, summary in enumerate(summaries, 1):
        item_id = summary.get("itemId")
        if not item_id:
            continue

        try:
            raw_detail = get_item_detail(token, item_id)
            if not is_buy_it_now_only(raw_detail):
                print(f"  [{idx}/{len(summaries)}] skipped {item_id}: not Buy It Now-only")
                continue

            record = {
                "source_url": raw_detail.get("itemWebUrl") or summary.get("itemWebUrl"),
                "api_payload": raw_detail,
            }

            out_path = _write_dataset_record(record)
            written += 1
            print(f"  [{idx}/{len(summaries)}] wrote {out_path}")
        except Exception as exc:
            print(f"  [{idx}/{len(summaries)}] FAILED {item_id}: {exc}")

        time.sleep(0.1)

    print(f"\nWrote {written} raw dataset record(s) to {DATASET_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch eBay raw API payloads with parity output shape")
    parser.add_argument("--query", help="eBay search query")
    parser.add_argument(
        "--limit",
        type=int,
        default=RESULTS_LIMIT,
        help="Maximum Buy It Now listings to process",
    )
    args = parser.parse_args()

    query = (args.query or "").strip() or input("Enter your eBay search query: ").strip()
    limit = max(1, args.limit)
    run(query, limit)
