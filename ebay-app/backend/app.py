"""
Flask backend. Run with: python app.py

Every visitor to the frontend calls THIS server (GET /api/listings),
never eBay directly. This server holds the eBay app credentials and
does the OAuth exchange itself - see ebay_client.py.

Endpoints:
  GET /api/listings?q=<keywords>&limit=<n>   -> mapped listing rows
  GET /api/health                            -> cache stats / sanity check
  GET /                                      -> serves the demo frontend
"""

import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

import cache_db
import ebay_client

# Matches the numeric item ID in any of eBay's listing URL shapes, e.g.
#   https://www.ebay.com/itm/1234567890
#   https://www.ebay.com/itm/Some-Title-Here/1234567890
#   https://www.ebay.com/itm/1234567890?hash=...&var=...
LEGACY_ID_RE = re.compile(r"/itm/(?:[^/?]+/)?(\d{9,15})")


def extract_legacy_item_id(url: str):
    match = LEGACY_ID_RE.search(url)
    return match.group(1) if match else None

app = Flask(__name__, static_folder="../frontend", static_url_path="")

cache_db.init_db()


def extract_aspect(aspects, name):
    """localizedAspects is a flat list of {name, value} pairs eBay uses
    for item specifics like Size, Brand, Department, etc."""
    for a in aspects or []:
        if a.get("name", "").strip().lower() == name.lower():
            return a.get("value")
    return None


def map_item(raw: dict) -> dict:
    """Map a raw Browse API getItem response to the 8 fields we care
    about: item id, name, condition, size, brand, description,
    creation time, seller, smallest category, location."""

    aspects = raw.get("localizedAspects", [])

    categories = raw.get("categories") or []
    # eBay returns categories ordered broad -> specific; the last one
    # is the leaf ("smallest") category.
    smallest_category = categories[-1]["categoryName"] if categories else None

    loc = raw.get("itemLocation") or {}
    location_parts = [
        loc.get("city"),
        loc.get("stateOrProvince"),
        loc.get("country"),
    ]
    location = ", ".join(p for p in location_parts if p) or None

    seller = raw.get("seller") or {}

    price_info = raw.get("price") or {}
    price = None
    price_note = None

    if price_info.get("value"):
        # Standard fixed-price / Buy It Now listing.
        price = f"{price_info.get('value')} {price_info.get('currency', '')}".strip()
    else:
        bid_info = raw.get("currentBidPrice") or {}
        marketing = raw.get("marketingPrice") or {}
        original_info = marketing.get("originalPrice") or {}

        if bid_info.get("value"):
            # Auction-format listing: no fixed price, only current bid.
            price = f"{bid_info.get('value')} {bid_info.get('currency', '')}".strip()
            price_note = "current bid (auction)"
        elif original_info.get("value"):
            price = f"{original_info.get('value')} {original_info.get('currency', '')}".strip()
            price_note = "listed price"
        elif raw.get("itemGroupType"):
            # Multi-variation listing (e.g. size/color options): the
            # parent item has no single price - each variation does,
            # via a separate getItemsByItemGroup call.
            price_note = "price varies by variation - not returned at item level"
        else:
            price_note = "no online price (contact seller / classified ad format)"

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
    }


@app.route("/api/listings")
def listings():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "missing required query param 'q'"}), 400

    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 50))
    except ValueError:
        return jsonify({"error": "'limit' must be an integer"}), 400

    try:
        summaries = ebay_client.search_items(query, limit=limit)
    except ebay_client.EbayAuthError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:  # network / eBay-side errors
        return jsonify({"error": f"eBay search failed: {e}"}), 502

    results = []
    errors = []
    for summary in summaries:
        item_id = summary.get("itemId")
        if not item_id:
            continue

        cached = cache_db.get_fresh(item_id)
        if cached:
            results.append(cached)
            continue

        try:
            raw = ebay_client.get_item(item_id)
        except Exception as e:
            errors.append({"item_id": item_id, "error": str(e)})
            continue

        mapped = map_item(raw)
        cache_db.put(item_id, mapped)
        results.append(mapped)

    return jsonify({"query": query, "count": len(results), "items": results, "errors": errors})


@app.route("/api/listing")
def listing_by_url():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "missing required query param 'url'"}), 400

    legacy_id = extract_legacy_item_id(url)
    if not legacy_id:
        return jsonify({
            "error": "couldn't find an item ID in that URL. "
                     "Expected something like https://www.ebay.com/itm/.../1234567890"
        }), 400

    cached = cache_db.get_fresh(legacy_id)
    if cached:
        return jsonify({"item": cached, "from_cache": True})

    try:
        raw = ebay_client.get_item_by_legacy_id(legacy_id)
    except ebay_client.EbayAuthError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"eBay lookup failed: {e}"}), 502

    mapped = map_item(raw)
    cache_db.put(legacy_id, mapped)
    return jsonify({"item": mapped, "from_cache": False})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", **cache_db.stats()})


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)