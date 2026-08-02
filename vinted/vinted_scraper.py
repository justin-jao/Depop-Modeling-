import argparse
import asyncio
import json
import shutil
import urllib.parse
from pathlib import Path

from crawlee import Request
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
)
from crawlee.router import Router
from playwright_stealth import Stealth

MAX_ITEMS = 20
SEARCH_TIMEOUT_MS = 10000
DETAIL_NETWORK_IDLE_TIMEOUT_MS = 5000
NAVIGATION_TIMEOUT_MS = 15000
SEARCH_SELECTOR = "a[href*='/items/']"
REQUEST_QUEUE_DIR = Path(__file__).resolve().parents[1] / "storage" / "request_queues" / "default"

router = Router[PlaywrightCrawlingContext]()


def _reset_request_queue_storage() -> None:
    if REQUEST_QUEUE_DIR.exists():
        shutil.rmtree(REQUEST_QUEUE_DIR, ignore_errors=True)


async def _extract_product_jsonld(page) -> dict | None:
    scripts = await page.locator('script[type="application/ld+json"]').evaluate_all(
        """elements => elements.map((el) => el.textContent || '').filter(Boolean)"""
    )

    for script_text in scripts:
        try:
            data = json.loads(script_text)
        except Exception:
            continue

        if isinstance(data, dict) and data.get("@type") == "Product":
            return data

        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("@type") == "Product":
                    return entry

    return None


@router.default_handler
async def handle_search(context: PlaywrightCrawlingContext) -> None:
    context.log.info(f"Stage 1: scanning search results at {context.request.url}")

    max_items = int(context.request.user_data.get("max_items", MAX_ITEMS))
    max_items = max(1, max_items)

    try:
        await context.page.wait_for_selector(SEARCH_SELECTOR, timeout=SEARCH_TIMEOUT_MS)
    except Exception:
        context.log.error("Item grid failed to load within timeout.")
        return

    links = await context.page.locator(SEARCH_SELECTOR).evaluate_all(
        """elements => elements.map((el) => el.href).filter(Boolean)"""
    )

    deduped: list[str] = []
    seen = set()
    for link in links:
        if not isinstance(link, str):
            continue
        if "/items/" not in link:
            continue
        if link in seen:
            continue
        seen.add(link)
        deduped.append(link)
        if len(deduped) >= max_items:
            break

    if not deduped:
        context.log.warning("No item URLs found to enqueue.")
        return

    await context.add_requests([Request.from_url(url, label="PRODUCT") for url in deduped])
    context.log.info(f"Successfully enqueued {len(deduped)} item links for Stage 2 processing.")


@router.handler("PRODUCT")
async def handle_product(context: PlaywrightCrawlingContext) -> None:
    context.log.info(f"Stage 2: processing {context.request.url}")

    try:
        await context.page.wait_for_load_state("networkidle", timeout=DETAIL_NETWORK_IDLE_TIMEOUT_MS)
    except Exception:
        pass

    payload_source = "json-ld"
    api_data = await _extract_product_jsonld(context.page)

    if api_data:
        await context.push_data(
            {
                "source_url": context.request.url,
                "api_payload": api_data,
                "payload_source": payload_source,
            }
        )
        context.log.info(f"Successfully retrieved the Vinted payload from {payload_source}.")
    else:
        context.log.warning("Could not extract a Vinted payload from the page.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Vinted listings and capture raw item payloads")
    parser.add_argument("--query", help="Vinted search query")
    parser.add_argument("--max-items", type=int, default=MAX_ITEMS, help="Number of item pages to process")
    parser.add_argument("--domain", default="vinted.co.uk", help="Vinted domain to scrape")
    args = parser.parse_args()

    query = (args.query or input("Enter your Vinted search query: ")).strip()
    domain = (args.domain or "vinted.co.uk").strip()
    max_items = max(1, args.max_items)

    encoded_query = urllib.parse.quote_plus(query)
    start_url = f"https://www.{domain}/catalog?search_text={encoded_query}&order=newest_first"

    _reset_request_queue_storage()

    crawler = PlaywrightCrawler(
        request_handler=router,
        headless=True,
        max_requests_per_crawl=max_items + 1,
        max_request_retries=1,
    )

    @crawler.pre_navigation_hook
    async def setup_page(context) -> None:
        stealth = Stealth()
        await stealth.apply_stealth_async(context.page)
        context.page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)

        async def block_heavy_assets(route) -> None:
            resource_type = route.request.resource_type
            if resource_type in {"image", "media", "font"}:
                await route.abort()
                return
            await route.continue_()

        await context.page.route("**/*", block_heavy_assets)

    print(f"\nStarting crawl for: '{query}' on {domain}...")
    await crawler.run(
        [
            Request.from_url(
                start_url,
                user_data={"max_items": max_items},
            )
        ]
    )
    print("\nCrawl complete.")


if __name__ == "__main__":
    asyncio.run(main())
