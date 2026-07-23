import asyncio
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

# How many listings we want back
MAX_LISTINGS = 5

# Every listing gets its own file in here: results/listing_<id>.json
OUTPUT_DIR = Path(__file__).parent / "results"


def parse_next_flight_chunks(chunks: list) -> list:
    """
    Vinted's item pages are Next.js App` Router pages, which ship their data
    as "RSC flight" chunks (`self.__next_f.push([id, "<chunk>"])`) rather
    than one clean JSON blob. Each chunk is joined together and then split
    into its numbered segments (`<id>:<payload>`); each payload is either a
    JSON value (sometimes prefixed with a single type letter like I/H/T) or
    something we can't use, which we just skip.

    Returns a list of every payload we could successfully json.loads().
    """
    joined = "".join(chunks)
    segments = re.split(r"(?m)^(?=[0-9a-fA-F]+:)", joined)

    parsed = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        m = re.match(r"^([0-9a-fA-F]+):(.*)$", seg, re.DOTALL)
        if not m:
            continue

        payload = m.group(2)
        candidates = [payload]
        if payload and payload[0].isalpha():
            # Some segments have a single leading type letter before the JSON.
            candidates.append(payload[1:])

        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate or candidate[0] not in "{[\"0123456789tfn-":
                continue
            try:
                parsed.append(json.loads(candidate))
                break
            except json.JSONDecodeError:
                continue

    return parsed


def _score_item_candidate(obj: dict, item_id: Any = None) -> int:
    """Heuristically score whether a dict looks like Vinted item-detail data."""
    score = 0

    candidate_id = obj.get("id")
    if item_id is not None and str(candidate_id) == str(item_id):
        score += 6

    hint_keys = [
        "description",
        "price",
        "status",
        "user",
        "catalog",
        "catalog_id",
        "brand_dto",
        "brand_title",
        "created_at",
        "created_at_ts",
        "updated_at",
        "updated_at_ts",
        "city",
        "country_title",
    ]
    for key in hint_keys:
        value = obj.get(key)
        if value not in (None, "", [], {}):
            score += 1

    return score


def _best_item_candidate_from_object(obj: Any, item_id: Any = None) -> Optional[dict]:
    """Recursively find the highest-scoring item-like dict in nested JSON."""
    best_obj = None
    best_score = 0

    def walk(value: Any) -> None:
        nonlocal best_obj, best_score
        if isinstance(value, dict):
            score = _score_item_candidate(value, item_id=item_id)
            if score > best_score:
                best_obj = value
                best_score = score

            nested_item = value.get("item")
            if isinstance(nested_item, dict):
                nested_score = _score_item_candidate(nested_item, item_id=item_id) + 1
                if nested_score > best_score:
                    best_obj = nested_item
                    best_score = nested_score

            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(obj)
    return best_obj if best_score >= 6 else None


def find_item_blob(parsed_objects: list, item_id: Any = None) -> Optional[dict]:
    """
    Recursively search the parsed flight-stream objects for the dict that
    actually represents the Vinted item - identified by having a
    "brand_dto" key (confirmed present via the keyword scan), since we don't
    know in advance where in the page's data tree it sits.
    """

    best_obj = None
    best_score = 0

    for parsed in parsed_objects:
        candidate = _best_item_candidate_from_object(parsed, item_id=item_id)
        if not isinstance(candidate, dict):
            continue
        score = _score_item_candidate(candidate, item_id=item_id)
        if score > best_score:
            best_obj = candidate
            best_score = score

    return best_obj


def _get(d, *path, default=None):
    """Safely walk a nested dict along `path`, returning `default` on any miss."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _dict_or_empty(value):
    return value if isinstance(value, dict) else {}


def _is_reference_token(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$") and ":" in value


def _deep_merge_dicts(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _derive_listing_status(item: dict, fallback: Optional[dict] = None) -> str:
    fallback = fallback or {}
    is_reserved = bool(_first_non_empty(item.get("is_reserved"), fallback.get("is_reserved"), False))
    closing_action = _first_non_empty(
        item.get("closing_action"),
        item.get("item_closing_action"),
        fallback.get("closing_action"),
        fallback.get("item_closing_action"),
    )
    is_visible = _first_non_empty(item.get("is_visible"), fallback.get("is_visible"), True)

    if closing_action:
        reason = closing_action.get("reason") if isinstance(closing_action, dict) else None
        return f"Closed ({reason})" if reason else "Closed"
    if is_reserved:
        return "Reserved"
    if is_visible is False:
        return "Closed"
    return "On sale"


def _build_item_location(item: dict, fallback: Optional[dict] = None) -> str:
    fallback = fallback or {}
    city = _first_non_empty(
        item.get("city"),
        _get(item, "user", "city"),
        fallback.get("city"),
        _get(fallback, "user", "city"),
    )
    country = _first_non_empty(
        _get(item, "user", "country_title"),
        item.get("country_title"),
        _get(item, "country", "title"),
        _get(item, "country", "name"),
        _get(fallback, "user", "country_title"),
        fallback.get("country_title"),
        _get(fallback, "country", "title"),
        _get(fallback, "country", "name"),
    )
    return ", ".join(filter(None, [city, country]))


async def fetch_item_detail_via_internal_api(
    context: PlaywrightCrawlingContext,
    *,
    domain: str,
    item_id: Any,
    referer_url: str,
) -> Optional[dict]:
    """Try known internal item endpoints and return a detail dict when available."""
    urls = [
        f"https://www.{domain}/api/v2/items/{item_id}",
        f"https://www.{domain}/api/v2/items/{item_id}?localize=true",
        f"https://www.{domain}/api/v2/catalog/items/{item_id}",
    ]

    for url in urls:
        try:
            response = await context.page.request.get(
                url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": referer_url,
                },
            )
        except Exception:
            continue

        if response.status != 200:
            continue

        try:
            payload = await response.json()
        except Exception:
            continue

        if isinstance(payload, dict):
            if isinstance(payload.get("item"), dict):
                return payload["item"]
            if _score_item_candidate(payload, item_id=item_id) >= 6:
                return payload

    return None


async def fetch_item_detail_from_page_api_responses(
    context: PlaywrightCrawlingContext,
    *,
    item_page_url: str,
    item_id: Any,
) -> Optional[dict]:
    """Capture JSON API responses triggered by the item page and extract item detail."""
    captured_candidates: list[dict] = []
    capture_tasks = []

    def on_response(response) -> None:
        url = response.url.lower()
        if "/api/" not in url:
            return

        content_type = (response.headers.get("content-type") or "").lower()
        if "json" not in content_type:
            return

        async def collect() -> None:
            try:
                payload = await response.json()
            except Exception:
                return

            candidate = _best_item_candidate_from_object(payload, item_id=item_id)
            if isinstance(candidate, dict):
                captured_candidates.append(candidate)

        capture_tasks.append(asyncio.create_task(collect()))

    context.page.on("response", on_response)
    try:
        await context.page.goto(item_page_url, wait_until="domcontentloaded", timeout=15000)
        try:
            await context.page.wait_for_load_state("networkidle", timeout=7000)
        except Exception:
            pass

        if capture_tasks:
            await asyncio.gather(*capture_tasks, return_exceptions=True)
    finally:
        context.page.remove_listener("response", on_response)

    if not captured_candidates:
        return None

    # Pick the richest candidate that most strongly matches the target item id.
    best = max(captured_candidates, key=lambda c: _score_item_candidate(c, item_id=item_id))
    return best


async def extract_item_metadata_from_scripts(
    context: PlaywrightCrawlingContext,
    *,
    item_id: Any,
) -> dict:
    """Extract metadata from inline script text around the matching item_id."""
    html = await context.page.content()
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
    text = "\n".join(scripts)

    marker = f'\\"item_id\\":{item_id}'
    positions = [m.start() for m in re.finditer(re.escape(marker), text)]
    if not positions:
        return {}

    def _snippet_score(snippet_text: str) -> int:
        hints = [
            '\\"description\\"',
            '\\"catalog_id\\"',
            '\\"brand_dto\\"',
            '\\"updated_at\\"',
            '\\"created_at\\"',
            '\\"city\\"',
            '\\"country_title\\"',
        ]
        return sum(1 for key in hints if key in snippet_text)

    snippets = []
    for idx in positions:
        candidate = text[max(0, idx - 30000) : idx + 250000]
        snippets.append((candidate, _snippet_score(candidate)))

    snippet, best_score = max(snippets, key=lambda t: t[1])
    if best_score == 0:
        return {}

    def _capture_any(patterns: list[str]) -> Optional[str]:
        for pattern in patterns:
            m = re.search(pattern, snippet, flags=re.DOTALL)
            if m:
                return m.group(1)
        return None

    def _decode(raw_value: Optional[str]) -> Optional[str]:
        if raw_value in (None, ""):
            return None
        try:
            return json.loads(f'"{raw_value}"')
        except Exception:
            return raw_value

    brand_id_raw = _capture_any([
        r'\\"brand_dto\\":\\{[^}]*\\"id\\":(\\d+)',
        r'"brand_dto":\{[^}]*"id":(\d+)',
    ])
    brand_title_raw = _capture_any([
        r'\\"brand_dto\\":\\{[^}]*\\"title\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"brand_dto":\{[^}]*"title":"((?:\\.|[^"\\])*)"',
    ])
    catalog_id_raw = _capture_any([
        r'\\"catalog_id\\":(\\d+)',
        r'"catalog_id":(\d+)',
    ])
    category_raw = _capture_any([
        r'"category":"((?:\\.|[^"\\])*)"',
    ])
    description_raw = _capture_any([
        r'\\"description\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"description":"((?:\\.|[^"\\])*)"',
    ])
    updated_at_raw = _capture_any([
        r'\\"updated_at\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"updated_at":"((?:\\.|[^"\\])*)"',
    ])
    created_at_raw = _capture_any([
        r'\\"created_at\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"created_at":"((?:\\.|[^"\\])*)"',
    ])
    city_raw = _capture_any([
        r'\\"city\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"city":"((?:\\.|[^"\\])*)"',
    ])
    country_raw = _capture_any([
        r'\\"country_title\\":\\"((?:\\\\.|[^"\\\\])*)\\"',
        r'"country_title":"((?:\\.|[^"\\])*)"',
    ])

    if not country_raw:
        country_raw = "United Kingdom" if "United Kingdom" in snippet else None

    out: dict[str, Any] = {}
    if brand_id_raw:
        out["brand_dto"] = {"id": int(brand_id_raw)}
    if brand_title_raw:
        out["brand_dto"] = out.get("brand_dto", {})
        out["brand_dto"]["title"] = _decode(brand_title_raw)
    if catalog_id_raw:
        out["catalog_id"] = int(catalog_id_raw)
    if category_raw and "catalog_id" not in out:
        out["catalog_title"] = _decode(category_raw)
    if description_raw:
        out["description"] = _decode(description_raw)
    if updated_at_raw:
        out["updated_at"] = _decode(updated_at_raw)
    if created_at_raw:
        out["created_at"] = _decode(created_at_raw)
    if city_raw:
        out["city"] = _decode(city_raw)
    if country_raw:
        out["country_title"] = _decode(country_raw)

    return out


def build_record(item: dict, fallback: Optional[dict] = None) -> dict:
    """
    Map Vinted's item-detail JSON onto the fields we care about.

    IMPORTANT: Vinted's API is private/unofficial and not documented. Field
    names can vary slightly by locale or change over time. Every field below
    is pulled defensively with .get()/fallbacks.
    """
    fallback = fallback or {}

    price = _first_non_empty(_get(item, "price", default=None), _get(fallback, "price", default=None), {})
    photo = _dict_or_empty(_first_non_empty(item.get("photo"), fallback.get("photo")))

    # Vinted's own "status" field is actually the item's CONDITION
    # (e.g. "New with tags", "Very good", "Good"), not its availability.
    condition = _first_non_empty(item.get("status"), fallback.get("status"))
    listing_status = _derive_listing_status(item, fallback=fallback)

    brand_id = _first_non_empty(
        _get(item, "brand_dto", "id"),
        item.get("brand_id"),
        _get(item, "brand", "id"),
        _get(fallback, "brand_dto", "id"),
        fallback.get("brand_id"),
        _get(fallback, "brand", "id"),
    )
    brand_name = _first_non_empty(
        _get(item, "brand_dto", "title"),
        item.get("brand_title"),
        _get(item, "brand", "title"),
        _get(item, "brand", "name"),
        _get(fallback, "brand_dto", "title"),
        fallback.get("brand_title"),
        _get(fallback, "brand", "title"),
        _get(fallback, "brand", "name"),
    )

    category = _first_non_empty(
        _get(item, "catalog", "title"),
        item.get("catalog_title"),
        item.get("catalog_name"),
        item.get("catalog_id"),
        _get(item, "catalog", "id"),
        _get(fallback, "catalog", "title"),
        fallback.get("catalog_title"),
        fallback.get("catalog_name"),
        fallback.get("catalog_id"),
        _get(fallback, "catalog", "id"),
    )

    seller_description = _first_non_empty(item.get("description"), fallback.get("description"))
    last_edited_at = _first_non_empty(
        item.get("updated_at"),
        item.get("updated_at_ts"),
        item.get("modified_at"),
        fallback.get("updated_at"),
        fallback.get("updated_at_ts"),
        fallback.get("modified_at"),
    )
    uploaded_at = _first_non_empty(
        item.get("created_at"),
        item.get("created_at_ts"),
        item.get("upload_date"),
        fallback.get("created_at"),
        fallback.get("created_at_ts"),
        fallback.get("upload_date"),
    )

    price_amount = price
    price_currency = _first_non_empty(item.get("currency"), fallback.get("currency"))
    if isinstance(price, dict):
        preferred_amount = _first_non_empty(price.get("amount"), price.get("value"), price.get("price"))
        fallback_price = _dict_or_empty(_get(fallback, "price", default={}))
        fallback_amount = _first_non_empty(fallback_price.get("amount"), fallback_price.get("value"), fallback_price.get("price"))
        price_amount = fallback_amount if _is_reference_token(preferred_amount) else preferred_amount
        price_currency = _first_non_empty(
            price.get("currency_code"),
            price.get("currency"),
            item.get("currency"),
            fallback.get("currency"),
        )

    return {
        "listing_id": item.get("id"),
        "user_id": _first_non_empty(_get(item, "user", "id"), _get(fallback, "user", "id")),
        "brand_id": brand_id,
        "brand_name": brand_name,
        "listing_status": listing_status,
        "category": category,
        "seller_description": seller_description,
        "last_edited_at": last_edited_at,
        "uploaded_at": uploaded_at,
        "thumbnail_url": photo.get("url") or photo.get("full_size_url"),
        "item_location": _build_item_location(item, fallback=fallback),
        "condition": condition,
        "price": {
            "amount": price_amount,
            "currency": price_currency,
        },
    }


async def handle_search(context: PlaywrightCrawlingContext) -> None:
    domain = context.request.user_data["domain"]
    query = context.request.user_data["query"]

    context.log.info(f"Loaded {context.request.url} - this establishes cookies/session for the API calls below")

    # Let the page settle so we have real session cookies (incl. any
    # anti-bot cookie) before we start calling the API directly.
    try:
        await context.page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    encoded_query = urllib.parse.quote_plus(query)
    catalog_url = (
        f"https://www.{domain}/api/v2/catalog/items"
        f"?search_text={encoded_query}&page=1&per_page={MAX_LISTINGS}&order=newest_first"
    )

    context.log.info(f"Requesting catalog API directly: {catalog_url}")

    # context.page.request shares cookies/session with the page we just
    # loaded, so this call is "logged in" as far as Vinted's session/anti-bot
    # cookies are concerned - but we control the exact URL and timing
    # ourselves instead of waiting to catch an incidental XHR.
    catalog_response = await context.page.request.get(
        catalog_url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": context.request.url,
        },
    )

    if catalog_response.status != 200:
        snippet = (await catalog_response.text())[:500]
        context.log.error(
            f"Catalog API returned HTTP {catalog_response.status} instead of 200. "
            f"This usually means anti-bot protection blocked the request "
            f"(try headless=False below) or the endpoint/params changed. "
            f"Response body snippet: {snippet!r}"
        )
        return

    try:
        catalog_payload = await catalog_response.json()
    except Exception as e:
        snippet = (await catalog_response.text())[:500]
        context.log.error(
            f"Catalog API returned HTTP 200 but the body wasn't valid JSON "
            f"(likely an HTML challenge page from anti-bot protection): {e}. "
            f"Body snippet: {snippet!r}"
        )
        return

    if not isinstance(catalog_payload, dict):
        context.log.error("Catalog API returned JSON with an unexpected top-level shape.")
        return

    items = catalog_payload.get("items", [])
    if not isinstance(items, list):
        context.log.error("Catalog API response field 'items' was not a list.")
        return

    context.log.info(f"Catalog API returned {len(items)} item(s).")

    if not items:
        context.log.warning(
            "Catalog API responded with HTTP 200 and valid JSON, but 0 items. "
            "Try a broader search query, or double check this domain actually "
            "has matching listings."
        )
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    saved = 0
    for item_summary in items[:MAX_LISTINGS]:
        if not isinstance(item_summary, dict):
            context.log.warning("Skipping a catalog item with an unexpected data shape.")
            continue

        item_id = item_summary.get("id")
        if item_id is None:
            continue

        # Build the record from the catalog summary itself. The old
        # /api/v2/items/{id} detail endpoint now 404s for every id (Vinted
        # appears to have removed/changed it), so we no longer depend on it.
        # build_record() pulls fields defensively, so whatever the summary
        # doesn't include (e.g. seller_description, which search summaries
        # typically omit) just comes back None.
        record = build_record(item_summary)

        # Best-effort enrichment: load the real listing page and try to pull
        # out whatever embedded JSON state the front-end ships with it, to
        # recover fields like the seller description and exact upload/edit
        # dates that search summaries don't include. This is speculative -
        # if it doesn't find a recognizable pattern, the catalog-based
        # record above is kept as-is.
        item_path = item_summary.get("path") or item_summary.get("url")
        if isinstance(item_path, str) and item_path:
            item_page_url = item_path if item_path.startswith("http") else f"https://www.{domain}{item_path}"
        else:
            item_page_url = f"https://www.{domain}/items/{item_id}"

        try:
            network_item_detail = await fetch_item_detail_from_page_api_responses(
                context,
                item_page_url=item_page_url,
                item_id=item_id,
            )

            # For the first item only, run a keyword scan of <script> tags to
            # help detect front-end payload shifts during troubleshooting.
            if item_id == items[0].get("id"):
                keyword_hits = await context.page.evaluate(
                    """() => {
                        const scripts = Array.from(document.querySelectorAll('script')).map(s => s.textContent || '');
                        const all = scripts.join('\\n');
                        const keywords = [
                            'description', 'brand_dto', 'created_at_ts', 'catalog_id',
                            'closing_action', '__NEXT_DATA__', '__NUXT__', 'self.__next_f'
                        ];
                        const hits = {};
                        for (const k of keywords) { hits[k] = all.includes(k); }
                        return hits;
                    }"""
                )
                context.log.info(f"Keyword scan of item page <script> tags: {keyword_hits}")

            # Vinted's item pages are Next.js App Router pages - the full
            # item data (description, brand_dto, dates, etc.) is shipped as
            # RSC "flight" chunks rather than a clean JSON blob. Pull the raw
            # chunks out and parse them ourselves.
            chunks = await context.page.evaluate(
                """() => {
                    try {
                        return (self.__next_f || [])
                            .map(pair => Array.isArray(pair) ? pair[1] : null)
                            .filter(Boolean);
                    } catch (e) { return []; }
                }"""
            )

            if not chunks:
                # Some pages do not expose self.__next_f at runtime (or it is
                # emptied quickly). Fall back to scraping push([...]) chunks
                # directly from inline script text.
                chunks = await context.page.evaluate(
                    r"""() => {
                        const scripts = Array.from(document.querySelectorAll('script'));
                        const out = [];
                        const re = /self\.__next_f\.push\(\[.*?,\s*("(?:\\\\.|[^"\\\\])*")\]\)/g;

                        for (const s of scripts) {
                            const text = s.textContent || '';
                            let m;
                            while ((m = re.exec(text)) !== null) {
                                try {
                                    out.push(JSON.parse(m[1]));
                                } catch (e) {
                                    // Ignore malformed captures.
                                }
                            }
                        }
                        return out;
                    }"""
                )

            parsed_objects = parse_next_flight_chunks(chunks)
            flight_item_detail = find_item_blob(parsed_objects, item_id=item_id)
            item_detail = flight_item_detail or network_item_detail

            if not item_detail:
                item_detail = await fetch_item_detail_via_internal_api(
                    context,
                    domain=domain,
                    item_id=item_id,
                    referer_url=item_page_url,
                )
                if item_detail:
                    context.log.info(f"Item {item_id}: built record from internal API fallback")

            script_metadata = await extract_item_metadata_from_scripts(context, item_id=item_id)

            if item_detail:
                merged_item = _deep_merge_dicts(item_summary, script_metadata or {})
                merged_item = _deep_merge_dicts(merged_item, item_detail)
                record = build_record(merged_item, fallback=item_summary)
                context.log.info(f"Item {item_id}: built enriched record from item detail payload")
            else:
                if script_metadata:
                    merged_item = _deep_merge_dicts(item_summary, script_metadata)
                    record = build_record(merged_item, fallback=item_summary)
                context.log.warning(
                    f"Item {item_id}: could not locate item detail payload from page/api sources, "
                    f"keeping the catalog-summary-based record"
                )
        except Exception as e:
            context.log.warning(f"Item {item_id}: couldn't load listing page for enrichment, skipping enrichment: {e}")

        await context.push_data(record)

        out_file = OUTPUT_DIR / f"listing_{item_id}.json"
        out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        saved += 1
        context.log.info(f"Saved {out_file.name}")

    context.log.info(f"Done - saved {saved} listing(s) to '{OUTPUT_DIR}/'")


async def main() -> None:
    query = input("Enter your Vinted search query: ").strip()

    # Hardcoded for now - Vinted runs separate national sites (vinted.de,
    # vinted.fr, etc.) with separate inventories/currencies, so we stick to
    # one domain rather than prompting per-run. Change this if you want a
    # different country's site.
    domain = "vinted.co.uk"

    encoded_query = urllib.parse.quote_plus(query)
    start_url = f"https://www.{domain}/catalog?search_text={encoded_query}&order=newest_first"

    crawler = PlaywrightCrawler(
        request_handler=handle_search,
        # Vinted runs bot-detection (Datadome). If the log shows the catalog
        # API returning a non-200 status or non-JSON body, set this to False
        # for one run so you can see what's happening / solve any challenge
        # manually, then flip it back to True.
        headless=True,
        max_requests_per_crawl=1,
    )

    print(f"\nStarting crawl for: '{query}' on {domain}...")
    await crawler.run(
        [Request.from_url(start_url, user_data={"domain": domain, "query": query})]
    )

    print(f"\nCrawl complete. Check the '{OUTPUT_DIR.name}/' folder for individual listing_<id>.json files.")


if __name__ == "__main__":
    asyncio.run(main())