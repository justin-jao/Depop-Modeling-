import os
import sqlite3
from decimal import Decimal, InvalidOperation

DB_PATH = os.environ.get("SQLITE_DB_PATH", "./data.db")
DEFAULT_EBAY_FEE_RATE = Decimal(os.environ.get("EBAY_ESTIMATED_FEE_RATE", "0.1325"))

SQL_QUERY = """
-- Replace this SQL with your own.
-- Example:
-- SELECT
--   COUNT(*) AS total_listings,
--   COALESCE(SUM(price), 0) AS total_revenue,
--   COALESCE(AVG(price), 0) AS average_revenue,
--   'USD' AS currency,
--   COUNT(price) AS listings_with_price
-- FROM listings
-- WHERE title LIKE '%' || ? || '%';
SELECT
  0 AS total_listings,
  0 AS total_revenue,
  0 AS average_revenue,
  'USD' AS currency
"""


def as_decimal(value, default="0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def as_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_decimal_input(prompt: str) -> Decimal:
    while True:
        try:
            return Decimal(input(prompt).strip())
        except (InvalidOperation, ValueError):
            print("  Please enter a valid number.")


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


def calculate_gross_margin(average_revenue: Decimal, piece_cost: Decimal, fee_rate: Decimal):
    fee_rate = max(Decimal("0"), min(fee_rate, Decimal("1")))
    estimated_fees = average_revenue * fee_rate
    net_revenue = average_revenue - estimated_fees
    if net_revenue <= 0:
        return estimated_fees, net_revenue, Decimal("0")
    gross_margin = ((net_revenue - piece_cost) / net_revenue) * Decimal("100")
    return estimated_fees, net_revenue, gross_margin


def get_listing_revenue_stats(db_path: str, sql_query: str, query: str) -> dict:
    params = (query,) if "?" in sql_query else ()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql_query, params).fetchone()

    if row is None:
        raise RuntimeError("SQL returned no rows. Update SQL_QUERY to return one aggregate row.")

    total_listings = as_int(row["total_listings"]) if "total_listings" in row.keys() else 0
    total_revenue = as_decimal(row["total_revenue"]) if "total_revenue" in row.keys() else Decimal("0")
    average_revenue = as_decimal(row["average_revenue"]) if "average_revenue" in row.keys() else Decimal("0")
    currency = str(row["currency"]) if "currency" in row.keys() and row["currency"] else "USD"

    sampled_buy_it_now = as_int(row["sampled_buy_it_now_listings"], total_listings) if "sampled_buy_it_now_listings" in row.keys() else total_listings
    sampled_results = as_int(row["sampled_results"], total_listings) if "sampled_results" in row.keys() else total_listings
    sample_target = as_int(row["sample_target"], sampled_results) if "sample_target" in row.keys() else sampled_results
    matching_results = as_int(row["matching_results"], total_listings) if "matching_results" in row.keys() else total_listings
    listings_with_price = as_int(row["listings_with_price"], sampled_buy_it_now) if "listings_with_price" in row.keys() else sampled_buy_it_now

    if "listings_without_price" in row.keys():
        listings_without_price = as_int(row["listings_without_price"])
    else:
        listings_without_price = max(sampled_buy_it_now - listings_with_price, 0)

    priced_avg = (
        as_decimal(row["priced_listing_average_revenue"])
        if "priced_listing_average_revenue" in row.keys()
        else (total_revenue / Decimal(listings_with_price) if listings_with_price > 0 else Decimal("0"))
    )

    return {
        "total_listings": total_listings,
        "sampled_buy_it_now_listings": sampled_buy_it_now,
        "sampled_results": sampled_results,
        "sample_target": sample_target,
        "matching_results": matching_results,
        "total_revenue": total_revenue,
        "average_revenue": average_revenue,
        "priced_listing_average_revenue": priced_avg,
        "currency": currency,
        "listings_with_price": listings_with_price,
        "listings_without_price": listings_without_price,
    }


def calculate_listing_volume(query: str, piece_cost: Decimal, db_path: str = DB_PATH) -> int:
    print(f"Fetching listing metrics for: {query}")
    revenue_stats = get_listing_revenue_stats(db_path, SQL_QUERY, query)

    total = revenue_stats["total_listings"]
    volume = describe_volume(total)
    estimated_fees, net_average_revenue, gross_margin = calculate_gross_margin(
        revenue_stats["average_revenue"], piece_cost, DEFAULT_EBAY_FEE_RATE
    )

    print(f"  Total listings: {total}")
    print("  Listing source: SQLite query")
    print(f"  Volume indicator: {volume}")
    print(
        "  Estimated total revenue: "
        f"{format_money(revenue_stats['total_revenue'], revenue_stats['currency'])}"
    )
    print(
        "  Average revenue per listing: "
        f"{format_money(revenue_stats['average_revenue'], revenue_stats['currency'])}"
    )
    print(
        f"  Estimated eBay fees at {DEFAULT_EBAY_FEE_RATE * Decimal('100'):.2f}%: "
        f"{format_money(estimated_fees, revenue_stats['currency'])}"
    )
    print(
        "  Average revenue after estimated fees: "
        f"{format_money(net_average_revenue, revenue_stats['currency'])}"
    )
    print(f"  Gross margin on your piece cost: {gross_margin.quantize(Decimal('0.01'))}%")

    if gross_margin < Decimal("50"):
        print("  You may want to skip buying this piece.")

    if volume in {"high", "very high"}:
        recommended_price = (revenue_stats["average_revenue"] * Decimal("0.8")).quantize(Decimal("1"))
        print("  Be sure to use competitive pricing on this one!")
        print(f"  Try listing it at {format_money(recommended_price, revenue_stats['currency'])}.")

    if revenue_stats["listings_without_price"] > 0 and revenue_stats["listings_with_price"] > 0:
        print(
            "  Average revenue among listings with price: "
            f"{format_money(revenue_stats['priced_listing_average_revenue'], revenue_stats['currency'])}"
        )

    print(
        f"  Revenue based on {revenue_stats['sampled_buy_it_now_listings']} listings "
        f"from {revenue_stats['sampled_results']} scanned results "
        f"(cap {revenue_stats['sample_target']}) "
        f"({revenue_stats['matching_results']} matches available)"
    )

    if revenue_stats["listings_without_price"] > 0:
        print(
            f"  Listings without price: {revenue_stats['listings_without_price']} "
            f"of {revenue_stats['sampled_buy_it_now_listings']}"
        )

    return total


if __name__ == "__main__":
    user_query = input("Enter your search query: ")
    piece_cost = parse_decimal_input("Enter your buying cost of your piece: ")
    calculate_listing_volume(user_query, piece_cost)
