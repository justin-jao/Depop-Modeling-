import asyncio
import json
import re
import urllib.parse
from pathlib import Path
from typing import Optional

from crawlee import RequestA
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

# How many listings we want back
MAX_LISTINGS = 10

# Every listing gets its own file in here: results/listing_<id>.json
OUTPUT_DIR = Path(__file__).parent / "results"


def parse_next_flight_chunks(chunks: list) -> list:
    """
    Vinted's item pages are Next.js App Router pages, which ship their data
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


def find_item_blob(parsed_objects: list) -> Optional[dict]:
    """
    Recursively search the parsed flight-stream objects for the dict that
    actually represents the Vinted item - identified by having a
    "brand_dto" key (confirmed present via the keyword scan), since we don't
    know in advance where in the page's data tree it sits.
    """

    def search(obj):
        if isinstance(obj, dict):
            if "brand_dto" in obj:
                return obj
            for v in obj.values():
                found = search(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = search(v)
                if found is not None:
                    return found
        return None

    for po in parsed_objects:
        found = search(po)
        if found is not None:
            return found
    return None


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


def build_record(item: dict) -> dict:
    """
    Map Vinted's item-detail JSON onto the fields we care about.

    IMPORTANT: Vinted's API is private/unofficial and not documented. Field
    names can vary slightly by locale or change over time. Every field below
    is pulled defensively with .get()/fallbacks, and the full raw payload is
    kept under "raw_payload" so you can re-derive anything that comes back
    as None after checking the actual response shape.
    """
    price = _get(item, "price", default={})
    photo = item.get("photo") or {}

    # Vinted's own "status" field is actually the item's CONDITION
    # (e.g. "New with tags", "Very good", "Good"), not its availability.
    condition = item.get("status")

    # Availability ("on sale" vs sold/reserved/removed) has to be derived
    # from separate flags rather than from "status".
    is_reserved = bool(item.get("is_reserved"))
    closing_action = item.get("closing_action") or item.get("item_closing_action")
    is_visible = item.get("is_visible", True)

    if closing_action:
        reason = closing_action.get("reason") if isinstance(closing_action, dict) else None
        listing_status = f"Closed ({reason})" if reason else "Closed"
    elif is_reserved:
        listing_status = "Reserved"
    elif is_visible is False:
        listing_status = "Not visible / removed"
    else:
        listing_status = "On sale"

    location_parts = [
        item.get("city"),
        _get(item, "user", "country_title", default=item.get("country_title")),
    ]

    return {
        "listing_id": item.get("id"),
        "user_id": _get(item, "user", "id"),
        "brand_id": _get(item, "brand_dto", "id"),
        "brand_name": _get(item, "brand_dto", "title", default=item.get("brand_title")),
        "listing_status": listing_status,
        "category": _get(item, "catalog", "title", default=item.get("catalog_id")),
        "seller_description": item.get("description"),
        "last_edited_at": item.get("updated_at") or item.get("updated_at_ts"),
        "uploaded_at": item.get("created_at") or item.get("created_at_ts"),
        "thumbnail_url": photo.get("url") or photo.get("full_size_url"),
        "item_location": ", ".join(filter(None, location_parts)),
        "condition": condition,
        "price": {
            "amount": price.get("amount") if isinstance(price, dict) else price,
            "currency": price.get("currency_code") if isinstance(price, dict) else item.get("currency"),
        },
        # Full raw payload kept for reference / manual field recovery.
        "raw_payload": item,
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

    # Dump one raw catalog item so we can see exactly what Vinted's search
    # API gives us - useful if any fields below need adjusting later.
    debug_path = OUTPUT_DIR / "_debug_catalog_item_sample.json"
    debug_path.write_text(json.dumps(items[0], indent=2, ensure_ascii=False), encoding="utf-8")

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
        # typically omit) just comes back None - see raw_payload for what
        # Vinted actually sent.
        record = build_record(item_summary)

        # Best-effort enrichment: load the real listing page and try to pull
        # out whatever embedded JSON state the front-end ships with it, to
        # recover fields like the seller description and exact upload/edit
        # dates that search summaries don't include. This is speculative -
        # if it doesn't find a recognizable pattern, the catalog-based
        # record above is kept as-is and the raw state (if any) is stashed
        # for inspection.
        item_path = item_summary.get("path") or item_summary.get("url")
        if isinstance(item_path, str) and item_path:
            item_page_url = item_path if item_path.startswith("http") else f"https://www.{domain}{item_path}"
        else:
            item_page_url = f"https://www.{domain}/items/{item_id}"

        try:
            await context.page.goto(item_page_url, wait_until="domcontentloaded", timeout=15000)

            # For the first item only, save real evidence to inspect instead of
            # guessing blindly: the full rendered HTML, and a keyword scan of
            # every <script> tag's contents.
            if item_id == items[0].get("id"):
                debug_html_path = OUTPUT_DIR / "_debug_item_page.html"
                debug_html_path.write_text(await context.page.content(), encoding="utf-8")
                context.log.info(f"Saved full item page HTML for inspection to {debug_html_path.name}")

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

            parsed_objects = parse_next_flight_chunks(chunks)
            item_detail = find_item_blob(parsed_objects)

            if item_id == items[0].get("id"):
                debug_parsed_path = OUTPUT_DIR / "_debug_parsed_flight_objects.json"
                debug_parsed_path.write_text(
                    json.dumps(parsed_objects, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
                )
                context.log.info(
                    f"Parsed {len(parsed_objects)} flight object(s), "
                    f"item blob {'FOUND' if item_detail else 'NOT found'} - "
                    f"see {debug_parsed_path.name}"
                )

            if item_detail:
                record = build_record(item_detail)
                record["_data_source"] = "next_flight_stream"
                context.log.info(f"Item {item_id}: built record from full item detail (flight stream)")
            else:
                context.log.warning(
                    f"Item {item_id}: could not locate item detail blob in the flight stream, "
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