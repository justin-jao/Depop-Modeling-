import base64
import html
import json
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

EBAY_ENV = os.environ.get("EBAY_ENV", "PRODUCTION").upper()  # PRODUCTION or SANDBOX
CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

_EBAY_URLS = {
    "SANDBOX": (
        "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        "https://api.sandbox.ebay.com/buy/browse/v1",
        "https://api.sandbox.ebay.com/commerce/taxonomy/v1",
    ),
    "PRODUCTION": (
        "https://api.ebay.com/identity/v1/oauth2/token",
        "https://api.ebay.com/buy/browse/v1",
        "https://api.ebay.com/commerce/taxonomy/v1",
    ),
}
OAUTH_URL, BROWSE_BASE, TAXONOMY_BASE = _EBAY_URLS.get(EBAY_ENV, _EBAY_URLS["PRODUCTION"])

DEFAULT_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


def _normalized_oauth_scope() -> str:
    """Normalize scope from env (supports whitespace/comma-separated values).

    Falls back to the minimal broadly-supported app scope.
    """
    raw = os.environ.get("EBAY_SCOPE", DEFAULT_OAUTH_SCOPE)
    cleaned = raw.strip().strip('"').strip("'")
    scopes = [s for s in re.split(r"[\s,]+", cleaned) if s]
    return " ".join(scopes) if scopes else DEFAULT_OAUTH_SCOPE


OAUTH_SCOPE = _normalized_oauth_scope()

OUTPUT_DIR = "storage/ebay_results"
SELLER_OUTPUT_DIR = "storage/ebay_sellers"
RESULTS_LIMIT = 10  # how many search results to pull full detail for
SEARCH_PAGE_SIZE = 200
BUY_IT_NOW_FILTER = "buyingOptions:{FIXED_PRICE}"


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
    }


def is_buy_it_now_only(item_summary: dict) -> bool:
    buying_options = set(item_summary.get("buyingOptions") or [])
    return "FIXED_PRICE" in buying_options and "AUCTION" not in buying_options


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
            "scope": OAUTH_SCOPE,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"eBay OAuth failed ({resp.status_code}): {resp.text}")

    return resp.json()["access_token"]


def search_items(token: str, query: str, limit: int):
    summaries = []
    offset = 0

    while len(summaries) < limit:
        page_limit = min(SEARCH_PAGE_SIZE, limit)
        resp = requests.get(
            f"{BROWSE_BASE}/item_summary/search",
            headers=_auth_headers(token),
            params={"q": query, "limit": page_limit, "offset": offset, "filter": BUY_IT_NOW_FILTER},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
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


def get_item_detail(token: str, item_id: str):
    resp = requests.get(
        f"{BROWSE_BASE}/item/{item_id}",
        headers=_auth_headers(token),
        params={"fieldgroups": "ADDITIONAL_SELLER_DETAILS"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_default_category_tree_id(token: str) -> str | None:
    resp = requests.get(
        f"{TAXONOMY_BASE}/get_default_category_tree_id",
        headers=_auth_headers(token),
        params={"marketplace_id": MARKETPLACE_ID},
        timeout=15,
    )
    resp.raise_for_status()
    return (resp.json() or {}).get("categoryTreeId")


def get_taxonomy_category_path(
    token: str,
    category_tree_id: str,
    category_id: str,
    cache: dict[str, str | None],
) -> str | None:
    if not category_id:
        return None
    if category_id in cache:
        return cache[category_id]

    try:
        resp = requests.get(
            f"{TAXONOMY_BASE}/category_tree/{category_tree_id}/get_category_subtree",
            headers=_auth_headers(token),
            params={"category_id": category_id},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json() or {}

        ancestors = payload.get("categoryTreeNodeAncestors") or []
        names = [
            (ancestor.get("category") or {}).get("categoryName")
            for ancestor in ancestors
            if (ancestor.get("category") or {}).get("categoryName")
        ]

        current_name = (
            ((payload.get("categoryTreeNode") or {}).get("category") or {}).get("categoryName")
        )
        if current_name:
            names.append(current_name)

        path = " > ".join(names) if names else None
        cache[category_id] = path
        return path
    except Exception as e:
        print(f"    (taxonomy lookup failed for category {category_id}: {e})")
        cache[category_id] = None
        return None


def get_leaf_category(raw: dict) -> tuple[str | None, str | None]:
    categories = raw.get("categories") or []
    if categories:
        leaf = categories[-1] or {}
        return leaf.get("categoryId"), leaf.get("categoryName")

    # Browse item detail can return flat category fields instead of "categories"
    # (e.g., categoryId + pipe-delimited categoryPath).
    category_id = raw.get("categoryId")
    category_path = raw.get("categoryPath")
    category_name = None
    if isinstance(category_path, str) and category_path.strip():
        category_name = category_path.split("|")[-1].strip() or None

    return category_id, category_name


def extract_aspect(aspects, name):
    return next(
        (
            a.get("value")
            for a in (aspects or [])
            if a.get("name", "").strip().lower() == name.lower()
        ),
        None,
    )


def extract_size(aspects) -> str | None:
    """Best-effort size extraction across common eBay aspect labels."""
    if not aspects:
        return None

    # Prefer exact, most useful user-facing size fields first.
    preferred_names = [
        "Size",
        "US Shoe Size",
        "UK Shoe Size",
        "EU Shoe Size",
        "Shoe Size",
        "Waist Size",
        "Inseam",
    ]
    for name in preferred_names:
        value = extract_aspect(aspects, name)
        if value:
            return value

    # Fallback: any aspect containing "size" except metadata-like labels.
    for aspect in aspects:
        aspect_name = (aspect.get("name") or "").strip().lower()
        if "size" not in aspect_name:
            continue
        if aspect_name in {"size type", "size scale"}:
            continue
        value = aspect.get("value")
        if value:
            return value

    return None


def clean_description(value: str | None) -> str | None:
    """Convert eBay HTML-like descriptions to plain text."""
    if not isinstance(value, str) or not value.strip():
        return None

    text = html.unescape(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", "")
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    cleaned = text.strip()
    return cleaned or None


def extract_seller_id(seller: dict) -> str | None:
    """Best-effort seller ID from Browse payload (often username only)."""
    if not seller:
        return None

    for key in ("sellerId", "seller_id", "id", "userId", "username"):
        value = seller.get(key)
        if value is not None:
            value_text = str(value).strip()
            if value_text:
                return value_text
    return None


def _normalize_stat_value(value):
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    if re.fullmatch(r"\d+\.\d+", text):
        return float(text)
    return text


def map_seller(raw: dict) -> dict | None:
    seller = raw.get("seller") or {}
    if not seller:
        return None

    seller_id = extract_seller_id(seller)
    username = seller.get("username") or seller_id

    return {
        "source": "ebay",
        "seller_id": seller_id,
        "username": username,
        "rating": _normalize_stat_value(
            seller.get("feedbackPercentage")
            or seller.get("positiveFeedbackPercent")
            or seller.get("sellerRating")
        ),
        "items_sold": _normalize_stat_value(
            seller.get("feedbackScore")
            or seller.get("itemsSold")
            or seller.get("soldItems")
            or seller.get("positiveFeedbackCount")
        ),
    }


def map_item(raw: dict) -> dict:
    aspects = raw.get("localizedAspects", [])
    leaf_category_id, leaf_category_name = get_leaf_category(raw)

    loc = raw.get("itemLocation") or {}
    location = ", ".join(filter(None, [loc.get("city"), loc.get("stateOrProvince"), loc.get("country")])) or None

    seller = raw.get("seller") or {}

    def _price_string(price_source: dict) -> str | None:
        return (
            f"{price_source.get('value')} {price_source.get('currency', '')}".strip()
            if price_source.get("value")
            else None
        )

    def _currency_code(price_source: dict) -> str | None:
        value = price_source.get("currency")
        if value is None:
            return None
        value_text = str(value).strip()
        return value_text or None

    price_info = raw.get("price") or {}
    currency = _currency_code(price_info)
    price = _price_string(price_info)
    if not price:
        bid_info = raw.get("currentBidPrice") or {}
        marketing = raw.get("marketingPrice") or {}
        original_info = marketing.get("originalPrice") or {}
        if _price_string(bid_info):
            price = _price_string(bid_info)
            currency = _currency_code(bid_info)
        elif _price_string(original_info):
            price = _price_string(original_info)
            currency = _currency_code(original_info)

    image = raw.get("image") or {}
    image_url = image.get("imageUrl")

    return {
        "listing_id": raw.get("legacyItemId") or raw.get("itemId"),
        "source": "ebay",
        "source_url": raw.get("itemWebUrl"),
        "title": raw.get("title"),
        "desc": clean_description(raw.get("description")),
        "price": price,
        "currency": currency,
        "brand": extract_aspect(aspects, "Brand"),
        "size": extract_size(aspects),
        "condition": raw.get("condition"),
        "created_at": raw.get("itemCreationDate"),
        "seller_id": extract_seller_id(seller),
        "username": seller.get("username"),
        "category": leaf_category_name,
        "location": location,
        "image_url": image_url,
    }


def run(query: str):
    print(f"Getting OAuth token ({EBAY_ENV})...")
    token = get_app_token()

    print(f"Searching eBay for: {query}")
    summaries = search_items(token, query, RESULTS_LIMIT)
    print(f"Found {len(summaries)} results, pulling full detail for each...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SELLER_OUTPUT_DIR, exist_ok=True)

    written = 0
    seller_written = 0
    seen_sellers = set()
    for i, summary in enumerate(summaries, 1):
        item_id = summary.get("itemId")
        if not item_id:
            continue
        try:
            raw = get_item_detail(token, item_id)
            if not is_buy_it_now_only(raw):
                print(f"  [{i}/{len(summaries)}] skipped {item_id}: not Buy It Now-only")
                continue
            mapped = map_item(raw)
            mapped["scraped_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            mapped["search_query"] = query

            filename = f"{mapped['listing_id'] or item_id}.json"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(mapped, f, indent=2, ensure_ascii=False)

            written += 1
            print(f"  [{i}/{len(summaries)}] wrote {filepath}")

            seller = map_seller(raw)
            seller_key = seller.get("seller_id") if seller else None
            if seller and not seller_key:
                seller_key = seller.get("username")
            if seller and seller_key and seller_key not in seen_sellers:
                seen_sellers.add(seller_key)
                seller_path = os.path.join(SELLER_OUTPUT_DIR, f"{seller_key}.json")
                with open(seller_path, "w", encoding="utf-8") as f:
                    json.dump(seller, f, indent=2, ensure_ascii=False)
                seller_written += 1
                print(f"    wrote seller {seller_path}")
        except Exception as e:
            print(f"  [{i}/{len(summaries)}] FAILED {item_id}: {e}")
        time.sleep(0.1)  # light pacing, be polite to the API

    print(f"\nWrote {written} listing files to ./{OUTPUT_DIR}/")
    print(f"Wrote {seller_written} seller files to ./{SELLER_OUTPUT_DIR}/")


if __name__ == "__main__":
    user_query = input("Enter your eBay search query: ")
    run(user_query)