import asyncio
import json
import os
import re
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

MAX_LISTINGS = 5
PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_DIR / "results"
OUTPUT_DIR = OUTPUT_ROOT / "listings"
SELLER_OUTPUT_DIR = OUTPUT_ROOT / "sellers"
SCRAPE_RUNS_PATH = OUTPUT_ROOT / "scrape_runs.jsonl"
RAW_LISTINGS_PATH = OUTPUT_ROOT / "raw_listings.jsonl"
VENV_PYTHON = PROJECT_DIR / "venv" / "bin" / "python"
VENV_DIR = PROJECT_DIR / "venv"
RUN_SCRIPT = PROJECT_DIR / "run.sh"
JSON_ACCEPT_HEADER = "application/json, text/plain, */*"


def use_project_interpreter() -> None:
    if not VENV_PYTHON.is_file():
        if not RUN_SCRIPT.is_file():
            raise RuntimeError("The project virtual environment is missing and run.sh could not be found.")
        os.execv(str(RUN_SCRIPT), [str(RUN_SCRIPT)])

    try:
        running_prefix = Path(sys.prefix).resolve()
        project_prefix = VENV_DIR.resolve()
    except OSError:
        return

    if running_prefix != project_prefix:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])


if __name__ == "__main__":
    use_project_interpreter()

from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _get(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, indent=2, ensure_ascii=False) + "\n")


def _replace_nulls(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dict):
        return {k: _replace_nulls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_nulls(item) for item in value]
    return value


def _relative_age_to_iso(text: Optional[str]) -> Optional[str]:
    if not isinstance(text, str):
        return None
    value = text.strip().lower()
    if not value:
        return None
    if value in {"just now", "now"}:
        return _now_iso()

    match = re.search(
        r"(\d+|an?|one)\s+(sec|secs|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|month|months|yr|year|years)\s+ago",
        value,
    )
    if not match:
        return None

    qty_raw = match.group(1)
    qty = 1 if qty_raw in {"a", "an", "one"} else int(qty_raw)
    unit = match.group(2)
    unit_map = {
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
        "w": 604800,
        "wk": 604800,
        "wks": 604800,
        "week": 604800,
        "weeks": 604800,
        "mo": 2629800,
        "month": 2629800,
        "months": 2629800,
        "yr": 31557600,
        "year": 31557600,
        "years": 31557600,
    }
    seconds = unit_map.get(unit)
    if not seconds:
        return None

    ts = datetime.now(timezone.utc).timestamp() - (qty * seconds)
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_created_at(value: Any) -> Optional[str]:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return _normalize_created_at(int(text))
    return text


def _price_and_currency(item: dict) -> tuple[Optional[str], Optional[str]]:
    price = _get(item, "price", default={})
    if isinstance(price, dict):
        amount = _first_non_empty(price.get("amount"), price.get("value"), price.get("price"))
        currency = _first_non_empty(price.get("currency_code"), price.get("currency"), item.get("currency"))
    else:
        amount = price
        currency = item.get("currency")

    amount_text = str(amount).strip() if amount not in (None, "", [], {}) else None
    currency_text = str(currency).strip() if currency not in (None, "", [], {}) else None
    return amount_text, currency_text


def _normalize_stat_value(value: Any) -> Any:
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


def _seller_metrics(user: dict) -> tuple[Any, Any]:
    rating = _first_non_empty(
        user.get("rating"),
        user.get("score"),
        user.get("average_rating"),
        user.get("reviews_rating"),
        _get(user, "stats", "rating"),
        _get(user, "feedback", "rating"),
    )
    items_sold = _first_non_empty(
        user.get("items_sold"),
        user.get("sold_items"),
        user.get("sales_count"),
        user.get("completed_sales"),
        _get(user, "stats", "sales"),
        _get(user, "statistics", "sold"),
        _get(user, "feedback", "sales"),
    )
    return _normalize_stat_value(rating), _normalize_stat_value(items_sold)


def _dom_seller_metrics(dom_meta: dict) -> tuple[Any, Any]:
    if not isinstance(dom_meta, dict):
        return None, None
    return _normalize_stat_value(dom_meta.get("sellerRating")), _normalize_stat_value(dom_meta.get("sellerVolume"))


async def _extract_dom_metadata(page) -> dict:
    return await page.evaluate(
        """() => {
            const out = { uploadedText: null, category: null, location: null, desc: null, sellerRating: null, sellerVolume: null };

            const uploadNode = document.querySelector('[itemprop="upload_date"]');
            if (uploadNode && uploadNode.textContent) {
                out.uploadedText = uploadNode.textContent.trim();
            }

            const descNode = document.querySelector('[itemprop="description"]');
            if (descNode && descNode.textContent) {
                out.desc = descNode.textContent.trim();
            }

            const crumbs = Array.from(document.querySelectorAll('.breadcrumbs__item span[itemprop="title"]'))
                .map((el) => (el.textContent || '').trim())
                .filter(Boolean);
            if (crumbs.length) {
                const leaf = crumbs[crumbs.length - 1];
                out.category = /margiela/i.test(leaf) && crumbs.length > 1 ? crumbs[crumbs.length - 2] : leaf;
            }

            const rows = Array.from(document.querySelectorAll('.details-list__item'));
            for (const row of rows) {
                const values = row.querySelectorAll('.details-list__item-value');
                if (values.length < 2) continue;
                const label = (values[0].textContent || '').trim().toLowerCase();
                const value = (values[1].textContent || '').trim();
                if (label.includes('location') && value) {
                    out.location = value;
                    break;
                }
            }

            const ld = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
            for (const script of ld) {
                const raw = (script.textContent || '').trim();
                if (!raw) continue;
                try {
                    const payload = JSON.parse(raw);
                    if (payload && payload['@type'] === 'Product' && payload.category && !out.category) {
                        out.category = String(payload.category).trim();
                    }
                    if (payload && payload['@type'] === 'Product' && payload.description && !out.desc) {
                        out.desc = String(payload.description).trim();
                    }
                } catch (_) {}
            }

            if (!out.desc) {
                const metaDesc = document.querySelector('meta[property="og:description"], meta[name="description"]');
                if (metaDesc && metaDesc.content) {
                    out.desc = metaDesc.content.trim();
                }
            }

            const ratingLabels = Array.from(document.querySelectorAll('.web_ui__Rating__label span'));
            for (const labelNode of ratingLabels) {
                const labelText = labelNode && labelNode.textContent ? labelNode.textContent.trim() : null;
                const container = labelNode && labelNode.closest('div') ? labelNode.closest('div').parentElement : null;
                const fullStars = container ? container.querySelectorAll('div[class*="web_ui__Rating__full"]').length : 0;
                const halfStars = container ? container.querySelectorAll('div[class*="web_ui__Rating__half"]').length : 0;

                if (labelText && (fullStars || halfStars || /^\\d+$/.test(labelText))) {
                    out.sellerRating = fullStars + (halfStars * 0.5);
                    out.sellerVolume = labelText;
                    break;
                }
            }

            return out;
        }"""
    )


async def _fetch_profile_location(
    context: PlaywrightCrawlingContext,
    *,
    profile_url: str,
    referer_url: str,
) -> Optional[str]:
    try:
        response = await context.page.request.get(
            profile_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": referer_url,
            },
        )
    except Exception:
        return None

    if response.status != 200:
        return None

    body = await response.text()
    match = re.search(r'data-testid="profile-location-info--content">([^<]+)<', body, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _build_record(
    item: dict,
    *,
    query: str,
    domain: str,
    source_url: str,
    dom_meta: dict,
    profile_location: Optional[str],
) -> dict:
    amount, currency = _price_and_currency(item)

    user = _get(item, "user", default={}) if isinstance(_get(item, "user", default={}), dict) else {}
    category = _first_non_empty(item.get("catalog_title"), _get(item, "catalog", "title"), dom_meta.get("category"))
    user_rating, user_items_sold = _seller_metrics(user)
    dom_rating, dom_items_sold = _dom_seller_metrics(dom_meta)

    location = _first_non_empty(
        item.get("location"),
        item.get("city"),
        dom_meta.get("location"),
        profile_location,
    )
    if not location:
        location = "United Kingdom" if domain.endswith("co.uk") else None

    created_at = _first_non_empty(item.get("created_at"), item.get("created_at_ts"))
    created_at = _normalize_created_at(created_at)
    if created_at is None:
        created_at = _relative_age_to_iso(dom_meta.get("uploadedText"))

    listing_id = _first_non_empty(item.get("id"), _get(item, "item", "id"))
    seller_rating = _first_non_empty(user_rating, dom_rating)
    seller_items_sold = _first_non_empty(user_items_sold, dom_items_sold)

    return {
        "listing_id": str(listing_id) if listing_id is not None else None,
        "source": "vinted",
        "source_url": source_url,
        "title": item.get("title"),
        "desc": _first_non_empty(item.get("description"), dom_meta.get("desc")),
        "price": amount,
        "currency": currency,
        "brand": _first_non_empty(item.get("brand_title"), _get(item, "brand_dto", "title")),
        "size": _first_non_empty(item.get("size_title"), item.get("size")),
        "condition": item.get("status"),
        "created_at": created_at,
        "seller_id": str(user.get("id")) if user.get("id") is not None else None,
        "username": _first_non_empty(user.get("login"), user.get("username"), user.get("slug")),
        "seller_rating": seller_rating,
        "seller_items_sold": seller_items_sold,
        "category": category,
        "location": location,
        "image_url": _first_non_empty(_get(item, "photo", "url"), _get(item, "photo", "full_size_url")),
        "scraped_at": _now_iso(),
        "search_query": query,
    }


def _build_seller_record(item: dict, dom_meta: dict) -> Optional[dict]:
    user = _get(item, "user", default={}) if isinstance(_get(item, "user", default={}), dict) else {}
    if not user:
        return None

    user_rating, user_items_sold = _seller_metrics(user)
    dom_rating, dom_items_sold = _dom_seller_metrics(dom_meta)
    seller_id = user.get("id")
    username = _first_non_empty(user.get("login"), user.get("username"), user.get("slug"))

    return {
        "source": "vinted",
        "seller_id": str(seller_id) if seller_id is not None else None,
        "username": username,
        "rating": _first_non_empty(user_rating, dom_rating),
        "items_sold": _first_non_empty(user_items_sold, dom_items_sold),
    }


async def handle_search(context: PlaywrightCrawlingContext) -> None:
    domain = context.request.user_data["domain"]
    query = context.request.user_data["query"]
    run_id = context.request.user_data["run_id"]
    start_time = context.request.user_data["start_time"]
    loaded_count = 0

    OUTPUT_ROOT.mkdir(exist_ok=True)

    try:
        await context.page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    encoded_query = urllib.parse.quote_plus(query)
    catalog_url = (
        f"https://www.{domain}/api/v2/catalog/items"
        f"?search_text={encoded_query}&page=1&per_page={MAX_LISTINGS}&order=newest_first"
    )

    response = await context.page.request.get(
        catalog_url,
        headers={"Accept": JSON_ACCEPT_HEADER, "Referer": context.request.url},
    )

    try:
        if response.status != 200:
            context.log.error(f"Catalog API returned HTTP {response.status}")
            return

        payload = await response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list) or not items:
            context.log.warning("Catalog API returned no items.")
            return

        OUTPUT_DIR.mkdir(exist_ok=True)
        SELLER_OUTPUT_DIR.mkdir(exist_ok=True)

        saved = 0
        seller_saved = 0
        seen_sellers = set()
        for summary in items[:MAX_LISTINGS]:
            if not isinstance(summary, dict):
                continue

            item_id = summary.get("id")
            if item_id is None:
                continue

            item_path = summary.get("path") or summary.get("url")
            item_page_url = (
                item_path if isinstance(item_path, str) and item_path.startswith("http")
                else f"https://www.{domain}{item_path}" if isinstance(item_path, str) and item_path
                else f"https://www.{domain}/items/{item_id}"
            )

            dom_meta = {}
            profile_location = None
            detail_page = await context.page.context.new_page()
            try:
                await detail_page.goto(item_page_url, wait_until="domcontentloaded", timeout=15000)
                try:
                    await detail_page.wait_for_load_state("networkidle", timeout=7000)
                except Exception:
                    pass
                dom_meta = await _extract_dom_metadata(detail_page)
            except Exception as exc:
                context.log.warning(f"Item {item_id}: page enrichment failed: {exc}")
            finally:
                await detail_page.close()

            profile_url = _get(summary, "user", "profile_url")
            if isinstance(profile_url, str) and profile_url.strip():
                profile_location = await _fetch_profile_location(
                    context,
                    profile_url=profile_url,
                    referer_url=item_page_url,
                )

            record = _build_record(
                summary,
                query=query,
                domain=domain,
                source_url=item_page_url,
                dom_meta=dom_meta if isinstance(dom_meta, dict) else {},
                profile_location=profile_location,
            )
            record = _replace_nulls(record)

            await context.push_data(record)
            out_file = OUTPUT_DIR / f"listing_{item_id}.json"
            out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

            seller_record = _build_seller_record(summary, dom_meta if isinstance(dom_meta, dict) else {})
            seller_key = None
            if seller_record:
                seller_record = _replace_nulls(seller_record)
                seller_key = seller_record.get("seller_id") or seller_record.get("username")
            if seller_record and seller_key and seller_key not in seen_sellers:
                seen_sellers.add(seller_key)
                seller_file = SELLER_OUTPUT_DIR / f"seller_{seller_key}.json"
                seller_file.write_text(json.dumps(seller_record, indent=2, ensure_ascii=False), encoding="utf-8")
                seller_saved += 1

            raw_listing_row = {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "source_url": item_page_url,
                "api_payload": {
                    "item_summary": summary,
                    "dom_meta": dom_meta if isinstance(dom_meta, dict) else {},
                    "profile_location": profile_location,
                },
                "loaded_at": _utc_now_iso(),
                "processed": False,
            }
            raw_listing_row = _replace_nulls(raw_listing_row)
            _append_jsonl(RAW_LISTINGS_PATH, raw_listing_row)
            loaded_count += 1

            saved += 1
            context.log.info(f"Saved {out_file.name}")

        context.log.info(f"Done - saved {saved} listing(s) to '{OUTPUT_DIR}/'")
        context.log.info(f"Done - saved {seller_saved} seller(s) to '{SELLER_OUTPUT_DIR}/'")
    finally:
        scrape_run_row = {
            "run_id": run_id,
            "search_query": query,
            "start_time": start_time,
            "finish_time": _utc_now_iso(),
            "Listing_count": loaded_count,
        }
        scrape_run_row = _replace_nulls(scrape_run_row)
        _append_jsonl(SCRAPE_RUNS_PATH, scrape_run_row)
        context.log.info(f"Updated loading-zone tables at {SCRAPE_RUNS_PATH} and {RAW_LISTINGS_PATH}")


async def main() -> None:
    query = input("Enter your Vinted search query: ").strip()
    domain = "vinted.co.uk"
    run_id = str(uuid.uuid4())
    start_time = _utc_now_iso()
    start_url = f"https://www.{domain}/catalog?search_text={urllib.parse.quote_plus(query)}&order=newest_first"

    crawler = PlaywrightCrawler(
        request_handler=handle_search,
        headless=True,
        max_requests_per_crawl=1,
    )

    print(f"\nStarting crawl for: '{query}' on {domain}...")
    await crawler.run(
        [
            Request.from_url(
                start_url,
                user_data={
                    "domain": domain,
                    "query": query,
                    "run_id": run_id,
                    "start_time": start_time,
                },
            )
        ]
    )
    print(f"\nCrawl complete. Check the '{OUTPUT_ROOT.name}/' folder for individual listing_<id>.json files.")


if __name__ == "__main__":
    asyncio.run(main())
