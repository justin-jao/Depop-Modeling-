import json
import sqlite3

def transform_raw_data(db_path: str = "depop_data.db") -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    cursor = conn.cursor()

    # Fetch rows in the raw landing zone that haven't been transformed yet
    cursor.execute("""
        SELECT rl.id, rl.source_url, rl.api_payload, rl.loaded_at, sr.search_query
        FROM raw_listings rl
        JOIN scrape_runs sr ON rl.run_id = sr.run_id
        WHERE rl.processed = 0
    """)
    raw_rows = cursor.fetchall()

    if not raw_rows:
        print("No new raw records to transform.")
        conn.close()
        return

    transformed_count = 0

    for row in raw_rows:
        payload = json.loads(row["api_payload"])
        search_query = row["search_query"]
        scraped_at = row["loaded_at"]

        # Target the array under 'objects'
        objects = payload.get("objects", [])

        for item in objects:
            listing_id = str(item.get("id")) if item.get("id") else None
            seller_id = str(item.get("user_id")) if item.get("user_id") else None

            if not listing_id or not seller_id:
                continue

            # Title is the slug, description is the raw description, created at is desc date. 
            title = item.get("slug", "Untitled Listing") 
            description = item.get("description", "")
            created_at = item.get("created_at")

            # Pricing extraction
            pricing = item.get("pricing", {})
            currency = pricing.get("currency", "USD")
            
            try:
                price_str = (
                    pricing.get("current_price", {})
                    .get("price_breakdown", {})
                    .get("price", {})
                    .get("amount", "0.00")
                )
                price_amount = float(price_str)
            except (ValueError, TypeError):
                price_amount = 0.0

            # Attributes
            brand = item.get("brand_name")
            attrs = item.get("attributes", {})
            condition = attrs.get("condition")

            # Size extraction (Grabs the first size entry)
            sizes = item.get("sizes", [])
            size = sizes[0].get("name") if sizes and isinstance(sizes, list) else None

            # 1. Upsert Seller (Using user_id as identifier)
            cursor.execute("""
                INSERT INTO sellers (seller_id, username, rating, items_sold)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(seller_id) DO NOTHING
            """, (seller_id, f"user_{seller_id}", None, None))

            # 2. Upsert Listing (Deduplicated on source + listing_id)
            cursor.execute("""
                INSERT INTO listings (
                    listing_id, source, source_url, title, description, price, currency,
                    brand, size, condition, created_at, seller_id, scraped_at, search_query
                )
                VALUES (?, 'depop', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, listing_id) DO UPDATE SET
                    price=excluded.price,
                    description=excluded.description,
                    condition=excluded.condition,
                    scraped_at=excluded.scraped_at
            """, (
                listing_id, row["source_url"], title, description, price_amount, currency,
                brand, size, condition, created_at, seller_id, scraped_at, search_query
            ))
            transformed_count += 1

        # Mark the raw payload as processed
        cursor.execute("UPDATE raw_listings SET processed = 1 WHERE id = ?", (row["id"],))

    conn.commit()
    conn.close()
    print(f"Transformed {len(raw_rows)} raw payload(s) into {transformed_count} normalized listing rows.")

if __name__ == "__main__":
    transform_raw_data()