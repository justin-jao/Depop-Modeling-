import sqlite3

def setup_database(db_path: str = "depop_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Enforce foreign key constraints, if no foreign key then query fails
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Scrape Runs - Tracks execution metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            run_id TEXT PRIMARY KEY,
            search_query TEXT,
            start_time DATETIME,
            finish_time DATETIME,
            listing_count INTEGER DEFAULT 0
        )
    """)

    # Raw JSON payloads from Crawlee
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            source_url TEXT,
            api_payload JSON,
            loaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        )
    """)

    # Normalized Sellers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            seller_id TEXT PRIMARY KEY,
            username TEXT,
            rating REAL,
            items_sold INTEGER
        )
    """)

    # Normalized Listings (with source column for future scaling)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            listing_id TEXT,
            source TEXT DEFAULT 'depop',
            source_url TEXT,
            title TEXT,
            description TEXT,
            price REAL,
            currency TEXT,
            brand TEXT,
            size TEXT,
            condition TEXT,
            created_at DATETIME,
            seller_id TEXT,
            scraped_at DATETIME,
            search_query TEXT,
            PRIMARY KEY (source, listing_id),
            FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == "__main__":
    setup_database()