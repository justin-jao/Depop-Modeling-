"""
str_calculator.py

Fetches the number of active eBay listings for a search query and uses
that count as a simple indicator of listing volume.

Setup:
    pip install requests python-dotenv
    cp .env.example .env   # fill in EBAY_CLIENT_ID / EBAY_CLIENT_SECRET

Optional env:
    EBAY_MAX_REQUESTS_PER_MINUTE=20

Run:
    python str_calculator.py
"""

import base64
import math
from decimal import Decimal, InvalidOperation
import os
import time
from collections import deque
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

EBAY_ENV = os.environ.get("EBAY_ENV", "PRODUCTION").upper()
CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

if EBAY_ENV == "SANDBOX":
    OAUTH_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.sandbox.ebay.com/buy/browse/v1"
else:
    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


MAX_EBAY_REQUESTS_PER_MINUTE = max(1, _env_int("EBAY_MAX_REQUESTS_PER_MINUTE", 20))
RATE_LIMIT_WINDOW_SECONDS = 60.0
SEARCH_PAGE_SIZE = 200
REVENUE_SAMPLE_SIZE = 1000
BUY_IT_NOW_FILTER = "buyingOptions:{FIXED_PRICE}"


class RequestRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.min_interval_seconds = window_seconds / max_requests
        self.request_times = deque()
        self.last_request_time = None

    def wait_for_slot(self) -> None:
        while True:
            now = time.monotonic()

            while self.request_times and now - self.request_times[0] >= self.window_seconds:
                self.request_times.popleft()

            wait_for_window = 0.0
            if len(self.request_times) >= self.max_requests:
                wait_for_window = self.window_seconds - (now - self.request_times[0])

            wait_for_spacing = 0.0
            if self.last_request_time is not None:
                wait_for_spacing = self.min_interval_seconds - (now - self.last_request_time)

            delay = max(wait_for_window, wait_for_spacing, 0.0)
            if delay <= 0:
                timestamp = time.monotonic()
                self.request_times.append(timestamp)
                self.last_request_time = timestamp
                return

            time.sleep(delay)


EBAY_REQUEST_LIMITER = RequestRateLimiter(
    max_requests=MAX_EBAY_REQUESTS_PER_MINUTE,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _request_with_rate_limit(method: str, url: str, **kwargs):
    EBAY_REQUEST_LIMITER.wait_for_slot()
    return requests.request(method=method, url=url, **kwargs)


def get_app_token() -> str:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set. "
            "Copy .env.example to .env and fill in your keys."
        )

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    response = _request_with_rate_limit(
        "post",
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
    if response.status_code != 200:
        raise RuntimeError(f"eBay OAuth failed ({response.status_code}): {response.text}")

    return response.json()["access_token"]


def search_items_page(token: str, query: str, limit: int, offset: int) -> dict:
    response = _request_with_rate_limit(
        "get",
        f"{BROWSE_BASE}/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        },
        params={"q": query, "limit": limit, "offset": offset, "filter": BUY_IT_NOW_FILTER},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def build_sample_offsets(total_results: int, sample_target: int, page_size: int) -> list[int]:
    if total_results <= 0 or sample_target <= 0 or page_size <= 0:
        return [0]

    total_pages = math.ceil(total_results / page_size)
    pages_to_sample = min(total_pages, math.ceil(sample_target / page_size))
    if pages_to_sample <= 1:
        return [0]

    max_page_index = total_pages - 1
    sampled_page_indexes = []
    for sample_index in range(pages_to_sample):
        page_index = round(sample_index * max_page_index / (pages_to_sample - 1))
        if sampled_page_indexes and page_index <= sampled_page_indexes[-1]:
            page_index = min(max_page_index, sampled_page_indexes[-1] + 1)
        sampled_page_indexes.append(page_index)

    return [page_index * page_size for page_index in sampled_page_indexes]


def is_buy_it_now_only(item_summary: dict) -> bool:
    buying_options = set(item_summary.get("buyingOptions") or [])
    return "FIXED_PRICE" in buying_options and "AUCTION" not in buying_options


def extract_listing_price(item_summary: dict) -> Tuple[Optional[Decimal], Optional[str]]:
    price_info = item_summary.get("price") or {}
    bid_info = item_summary.get("currentBidPrice") or {}
    marketing = item_summary.get("marketingPrice") or {}
    original_info = marketing.get("originalPrice") or {}

    for price_source in (price_info, bid_info, original_info):
        value = price_source.get("value")
        currency = price_source.get("currency")
        if value is None or not currency:
            continue
        try:
            return Decimal(str(value)), currency
        except (InvalidOperation, ValueError):
            continue

    return None, None


def print_revenue_progress(processed_count: int, sample_target: int, total_results: int, listings_with_price: int) -> None:
    percent_complete = 0.0
    if sample_target > 0:
        percent_complete = min((processed_count / sample_target) * 100, 100.0)

    print(
        f"  Progress: {processed_count}/{sample_target} sampled listings "
        f"({percent_complete:.1f}%) from {total_results} total, {listings_with_price} with price"
    )


def print_buy_it_now_progress(processed_count: int, total_results: int, buy_it_now_count: int, listings_with_price: int) -> None:
    percent_complete = 0.0
    if total_results > 0:
        percent_complete = min((processed_count / total_results) * 100, 100.0)

    print(
        f"  Progress: scanned {processed_count}/{total_results} FIXED_PRICE results "
        f"({percent_complete:.1f}%), {buy_it_now_count} Buy It Now-only, {listings_with_price} with price"
    )


def get_listing_revenue_stats(token: str, query: str) -> dict:
    total_results = None
    sample_target = 0
    sampled_total_revenue = Decimal("0")
    currency = None
    seen_listing_ids = set()
    buy_it_now_only_count = 0
    listings_with_price = 0
    sample_offsets = [0]

    while sample_offsets:
        offset = sample_offsets.pop(0)
        page = search_items_page(token, query, SEARCH_PAGE_SIZE, offset)
        if total_results is None:
            total_results = page.get("total", 0)
            sample_target = min(REVENUE_SAMPLE_SIZE, total_results)
            sample_offsets = build_sample_offsets(total_results, sample_target, SEARCH_PAGE_SIZE)
            if sample_offsets and sample_offsets[0] == offset:
                sample_offsets.pop(0)
            print(
                f"  Scanning up to {sample_target} of {total_results} FIXED_PRICE search results "
                f"for Buy It Now-only revenue..."
            )

        item_summaries = page.get("itemSummaries") or []
        if not item_summaries:
            break

        for item_summary in item_summaries:
            if len(seen_listing_ids) >= sample_target:
                break

            listing_id = item_summary.get("itemId") or item_summary.get("legacyItemId")
            if not listing_id or listing_id in seen_listing_ids:
                continue

            seen_listing_ids.add(listing_id)
            if not is_buy_it_now_only(item_summary):
                continue

            buy_it_now_only_count += 1
            price_value, price_currency = extract_listing_price(item_summary)
            if price_value is None:
                continue

            if currency is None:
                currency = price_currency
            if price_currency != currency:
                raise RuntimeError(
                    f"Mixed currencies returned for query {query!r}: {currency} and {price_currency}."
                )

            sampled_total_revenue += price_value
            listings_with_price += 1

        print_buy_it_now_progress(
            processed_count=len(seen_listing_ids),
            total_results=sample_target,
            buy_it_now_count=buy_it_now_only_count,
            listings_with_price=listings_with_price,
        )
        if len(seen_listing_ids) >= sample_target:
            break

    sampled_listing_count = len(seen_listing_ids)
    scale_factor = Decimal("1")
    if sampled_listing_count > 0 and total_results:
        scale_factor = Decimal(total_results) / Decimal(sampled_listing_count)

    estimated_total_revenue = sampled_total_revenue * scale_factor
    average_revenue = Decimal("0")
    priced_listing_average_revenue = Decimal("0")
    if buy_it_now_only_count > 0:
        average_revenue = sampled_total_revenue / Decimal(buy_it_now_only_count)
    if listings_with_price > 0:
        priced_listing_average_revenue = sampled_total_revenue / Decimal(listings_with_price)

    return {
        "total_listings": total_results or 0,
        "sampled_buy_it_now_listings": buy_it_now_only_count,
        "sampled_results": sampled_listing_count,
        "sample_target": sample_target,
        "matching_results": total_results or 0,
        "total_revenue": estimated_total_revenue,
        "average_revenue": average_revenue,
        "priced_listing_average_revenue": priced_listing_average_revenue,
        "currency": currency or "USD",
        "listings_with_price": listings_with_price,
        "listings_without_price": buy_it_now_only_count - listings_with_price,
        "is_estimate": True,
    }


def format_money(amount: Decimal, currency: str) -> str:
    return f"{amount.quantize(Decimal('0.01'))} {currency}"


def describe_volume(total_listings: int) -> str:
    if total_listings < 100:
        return "low"
    if total_listings < 1000:
        return "moderate"
    if total_listings < 10000:
        return "high"
    return "very high"


def calculate_listing_volume(query: str) -> int:
    print(f"Getting OAuth token ({EBAY_ENV})...")
    token = get_app_token()

    print(f"Fetching listing metrics for: {query}")
    revenue_stats = get_listing_revenue_stats(token, query)
    total = revenue_stats["total_listings"]
    volume = describe_volume(total)

    print(f"  Total listings: {total}")
    print("  Listing type: Buy It Now only (auctions excluded)")
    print(f"  Volume indicator: {volume}")
    print(
        f"  Estimated total revenue across Buy It Now listings: "
        f"{format_money(revenue_stats['total_revenue'], revenue_stats['currency'])}"
    )
    print(
        f"  Average revenue per Buy It Now listing: "
        f"{format_money(revenue_stats['average_revenue'], revenue_stats['currency'])}"
    )
    if revenue_stats["listings_without_price"] > 0 and revenue_stats["listings_with_price"] > 0:
        print(
            f"  Average revenue among sampled listings with price: "
            f"{format_money(revenue_stats['priced_listing_average_revenue'], revenue_stats['currency'])}"
        )
    print(
        f"  Revenue based on {revenue_stats['sampled_buy_it_now_listings']} Buy It Now-only listings "
        f"from {revenue_stats['sampled_results']} scanned results "
        f"(cap {revenue_stats['sample_target']}) "
        f"({revenue_stats['matching_results']} FIXED_PRICE matches available)"
    )
    if revenue_stats["listings_without_price"] > 0:
        print(
            f"  Sampled listings without price: {revenue_stats['listings_without_price']} "
            f"of {revenue_stats['sampled_buy_it_now_listings']}"
        )
    return total


if __name__ == "__main__":
    user_query = input("Enter your eBay search query: ")
    calculate_listing_volume(user_query)