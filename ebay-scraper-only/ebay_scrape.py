import base64
import json
import os
import time

import requests
from dotenv import load_dotenv

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

OUTPUT_DIR = "ebay_results"
RESULTS_LIMIT = 10  # how many search results to pull full detail for


def get_app_token() -> str:
    """OAuth client-credentials flow - one token for this whole run."""
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


def search_items(token: str, query: str, limit: int):
    resp = requests.get(
        f"{BROWSE_BASE}/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        },
        params={"q": query, "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("itemSummaries", [])


def get_item_detail(token: str, item_id: str):
    resp = requests.get(
        f"{BROWSE_BASE}/item/{item_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def extract_aspect(aspects, name):
    for a in aspects or []:
        if a.get("name", "").strip().lower() == name.lower():
            return a.get("value")
    return None


def map_item(raw: dict) -> dict:
    aspects = raw.get("localizedAspects", [])

    categories = raw.get("categories") or []
    smallest_category = categories[-1]["categoryName"] if categories else None

    loc = raw.get("itemLocation") or {}
    location = ", ".join(
        p for p in [loc.get("city"), loc.get("stateOrProvince"), loc.get("country")] if p
    ) or None

    seller = raw.get("seller") or {}

    price_info = raw.get("price") or {}
    price = None
    price_note = None
    if price_info.get("value"):
        price = f"{price_info.get('value')} {price_info.get('currency', '')}".strip()
    else:
        bid_info = raw.get("currentBidPrice") or {}
        marketing = raw.get("marketingPrice") or {}
        original_info = marketing.get("originalPrice") or {}
        if bid_info.get("value"):
            price = f"{bid_info.get('value')} {bid_info.get('currency', '')}".strip()
            price_note = "current bid (auction)"
        elif original_info.get("value"):
            price = f"{original_info.get('value')} {original_info.get('currency', '')}".strip()
            price_note = "listed price"
        elif raw.get("itemGroupType"):
            price_note = "price varies by variation - not returned at item level"
        else:
            price_note = "no online price (contact seller / classified ad format)"

    image = raw.get("image") or {}
    image_url = image.get("imageUrl")

    return {
        "item_id": raw.get("legacyItemId") or raw.get("itemId"),
        "name": raw.get("title"),
        "condition": raw.get("condition"),
        "size": extract_aspect(aspects, "Size"),
        "brand": extract_aspect(aspects, "Brand"),
        "price": price,
        "price_note": price_note,
        "description": raw.get("description"),
        "creation_time": raw.get("itemCreationDate"),
        "seller_name": seller.get("username"),
        "category": smallest_category,
        "location": location,
        "url": raw.get("itemWebUrl"),
        "image_url": image_url,
    }


def download_image_base64(image_url: str):
    """Download a listing's image and return it as a base64 data URI
    string (e.g. 'data:image/jpeg;base64,...'), or None on failure."""
    if not image_url:
        return None
    try:
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        encoded = base64.b64encode(resp.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except Exception as e:
        print(f"    (image download failed: {e})")
        return None


def run(query: str):
    print(f"Getting OAuth token ({EBAY_ENV})...")
    token = get_app_token()

    print(f"Searching eBay for: {query}")
    summaries = search_items(token, query, RESULTS_LIMIT)
    print(f"Found {len(summaries)} results, pulling full detail for each...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    written = 0
    for i, summary in enumerate(summaries, 1):
        item_id = summary.get("itemId")
        if not item_id:
            continue
        try:
            raw = get_item_detail(token, item_id)
            mapped = map_item(raw)

            if mapped.get("image_url"):
                mapped["image_base64"] = download_image_base64(mapped["image_url"])
            else:
                mapped["image_base64"] = None

            filename = f"{mapped['item_id'] or item_id}.json"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(mapped, f, indent=2, ensure_ascii=False)

            written += 1
            has_image = " + image" if mapped["image_base64"] else ""
            print(f"  [{i}/{len(summaries)}] wrote {filepath}{has_image}")
        except Exception as e:
            print(f"  [{i}/{len(summaries)}] FAILED {item_id}: {e}")
        time.sleep(0.1)  # light pacing, be polite to the API

    print(f"\nWrote {written} listing files to ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    user_query = input("Enter your eBay search query: ")
    run(user_query)