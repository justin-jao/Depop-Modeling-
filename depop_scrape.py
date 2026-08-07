import asyncio
from multiprocessing import context
import re
import urllib.parse
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
    PlaywrightPreNavCrawlingContext,
)
from crawlee.browsers import BrowserPool, PlaywrightBrowserPlugin
from crawlee.router import Router
from playwright_stealth import Stealth

# Initialize the Router to coordinate Stage 1 (search) and Stage 2 (products)
router = Router[PlaywrightCrawlingContext]()


# --- STAGE 1: Search Grid Handler ---
# changed selector because product grid was updated, using partial match now, TEST AGAIN IN FUTURE
@router.default_handler
async def handle_search(context: PlaywrightCrawlingContext) -> None:
    context.log.info(f"Stage 1: Scanning search results at {context.request.url}")

    # Use a partial CSS match (*=) for 'productGrid' to ignore the random hash
    # and wait directly for a valid product link inside it
    robust_selector = 'ol[class*="productGrid"] a[href*="/products/"]'

    try:
        await context.page.wait_for_selector(
            robust_selector, timeout=10000
        )
    except Exception:
        context.log.error("Product grid failed to load within timeout.")
        return

    # Automatically find, deduplicate, and enqueue all product links
    await context.enqueue_links(
        selector=robust_selector,
        label="PRODUCT",
    )
    context.log.info("Successfully enqueued product links for Stage 2 processing.")


# --- STAGE 2: Individual Product Listing Handler ---
@router.handler("PRODUCT")
async def handle_product(context: PlaywrightCrawlingContext) -> None:
    context.log.info(f"Stage 2: Processing {context.request.url}")

    # Give the browser up to 5 seconds for background API fetches to settle
    try:
        await context.page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass  # If networkidle times out, we still check if the data was caught earlier

    # Retrieve the JSON payload we intercepted in the pre-navigation hook
    api_data = context.request.user_data.get("similar_products_api")

    if api_data:
        context.log.info("Successfully retrieved the targeted Depop API payload!")

        # Save the scraped URL and the clean JSON directly to Crawlee's dataset
        await context.push_data(
            {"source_url": context.request.url, "api_payload": api_data}
        )
    else:
        context.log.warning(
            "Did not intercept the target /similar/ API request on this page."
        )


async def main() -> None:
    # Get user input and format the Depop search URL
    query = input("Enter your Depop search query: ")
    encoded_query = urllib.parse.quote_plus(query)
    start_url = f"https://www.depop.com/search/?q={encoded_query}"

    # Initialize the Playwright Crawler
    crawler = PlaywrightCrawler(
        request_handler=router,
        # Set headless=True when you are ready to run this silently in the background (status code 403)
        headless=True,
        # Limit total requests during testing so it doesn't scrape thousands of items
        max_requests_per_crawl=15,
    )

    # --- PRE-NAVIGATION HOOK ---
    # Registering using the Python decorator syntax so it attaches directly to the crawler instance.
    # This runs BEFORE page.goto(), guaranteeing we catch early network requests.
    @crawler.pre_navigation_hook
    async def setup_network_interception(context: PlaywrightPreNavCrawlingContext,) -> None:

        # hides the fact that we are using a headless browser, making it less likely to be blocked by anti-bot measures
        stealth = Stealth()
        await stealth.apply_stealth_async(context.page)

        # Only attach the listener if we are navigating to a Stage 2 product page
        if context.request.label == "PRODUCT":

            async def on_response(response):
                # Filter for successful HTTP 200 GET requests
                if response.status == 200 and response.request.method == "GET":

                    # Match the specific Depop API URL structure using regex
                    # Target: webapi.depop.com/presentation/api/v1/products/<ANY_ID>/similar/
                    url_pattern = (
                        r"webapi\.depop\.com/presentation/api/v1/products/\d+/similar/"
                    )

                    if re.search(url_pattern, response.url):
                        context.log.info(
                            f"Target API request intercepted! URL: {response.url}"
                        )
                        try:
                            # Parse the JSON payload and stash it in user_data
                            data = await response.json()
                            context.request.user_data["similar_products_api"] = data
                        except Exception as e:
                            context.log.error(
                                f"Failed to parse JSON from target API: {e}"
                            )

            # Attach the listener to the browser page
            context.page.on("response", on_response)

    print(f"\nStarting crawl for: '{query}'...")
    await crawler.run([start_url])
    print(
        "\nCrawl complete."
    )


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())