import sqlite3
import pandas as pd

def test_pipeline_data(db_path: str = "depop_data.db"):
    # Connect to the database
    conn = sqlite3.connect(db_path)

    print("=== PIPELINE DATA VERIFICATION ===\n")

    try:
        # 1. Inspect the Loading Stage (raw_listings)
        print("--- 1. LOAD STAGE (raw_listings) ---")
        df_raw = pd.read_sql_query("SELECT * FROM raw_listings", conn)
        
        if df_raw.empty:
            print("Status: EMPTY. No raw data loaded.")
        else:
            print(f"Total Raw Payloads Loaded: {len(df_raw)}")
            print(f"Processed Status Breakdown:\n{df_raw['processed'].value_counts().to_string()}")
            print("\nPreview of raw_listings:")
            # Displaying everything except the massive JSON payload for readability
            print(df_raw[['id', 'run_id', 'source_url', 'processed', 'loaded_at']].head())
        
        print("\n" + "="*50 + "\n")
        # Inspect the Transformation Stage (listings)
        print("--- 2. TRANSFORM STAGE (sellers) ---")
        df_sellers = pd.read_sql_query("SELECT * FROM sellers", conn)
        
        if df_sellers.empty:
            print("Status: EMPTY. No sellers extracted.")
        else:
            print(f"Total Unique Sellers: {len(df_sellers)}")
            
            # Since our transform sets rating/items_sold to None, let's verify that behavior
            missing_ratings = df_sellers['rating'].isna().sum()
            print(f"Sellers missing ratings: {missing_ratings} / {len(df_sellers)}")
            
            print("\nPreview of sellers:")
            print(df_sellers.head())

        print("\n" + "="*50 + "\n")
        # Inspect the Transformation Stage (listings)
        
        print("---  Listings Table  ---")
        df_listings = pd.read_sql_query("SELECT * FROM listings", conn)
        
        if df_listings.empty:
            print("Status: EMPTY. No data was transformed.")
        else:
            print(f"Total Normalized Listings: {len(df_listings)}")
            
            # Check if our new columns populated correctly
            missing_descriptions = df_listings['description'].isna().sum()
            missing_created = df_listings['created_at'].isna().sum()
            print(f"Listings missing descriptions: {missing_descriptions}")
            print(f"Listings missing created_at: {missing_created}")
            
            print("\nPreview of listings (Key Columns):")       
            # Selecting a subset of columns to fit nicely in the terminal
            cols_to_show = ['listing_id', 'title', 'price', 'brand', 'created_at', 'description']
            print(df_listings[cols_to_show].head())
            # Find only columns that have at least one NaN value
            cols_to_show = df_listings.columns[df_listings.isna().any()].tolist()
            
            """if cols_to_show:
                print(f"\nPreview of listings (Only showing columns with NaN values: {cols_to_show}):")
                print(df_listings[cols_to_show].head())
            else:
                print("\nNo columns contain NaN values! All fields are fully populated.")"""
    except Exception as e:
        print(f"Error reading from database: {e}")
    finally:
        conn.close()
    

def clear_all_rows(db_path: str = "depop_data.db"):
    conn = sqlite3.connect(db_path)
    
    # Enforce foreign keys during the operation
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        #Delete child tables before parent tables
        cursor.execute("DELETE FROM listings;")
        cursor.execute("DELETE FROM sellers;")
        cursor.execute("DELETE FROM raw_listings;")
        cursor.execute("DELETE FROM scrape_runs;")
        
        conn.commit()
        print("✔ All rows successfully deleted. Schema remains intact.")
    except Exception as e:
        print(f"❌ Error deleting rows: {e}")
    finally:
        conn.close()

def reset_transform_stage(db_path: str = "depop_data.db") -> None:
    """
    Wipes normalized tables (listings, sellers) and resets the processed flag 
    in raw_listings to allow re-testing of the transform pipeline.
    """
    conn = sqlite3.connect(db_path)
    # Enable foreign keys so SQLite enforces constraint rules
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        # 1. Wipe listings first (child table that references sellers)
        cursor.execute("DELETE FROM listings;")
        deleted_listings = cursor.rowcount

        # 2. Wipe sellers (parent table)
        cursor.execute("DELETE FROM sellers;")
        deleted_sellers = cursor.rowcount

        # 3. Reset the processed flag in the raw landing zone
        cursor.execute("UPDATE raw_listings SET processed = 0;")
        reset_raw = cursor.rowcount

        conn.commit()
        print("=== TRANSFORM STAGE RESET COMPLETE ===")
        print(f"Removed {deleted_listings} rows from 'listings'.")
        print(f"Removed {deleted_sellers} rows from 'sellers'.")
        print(f"Reset 'processed = 0' for {reset_raw} rows in 'raw_listings'.")
        print("\nYou can now run transform.py to re-test your column mapping!")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error during reset: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_pipeline_data()
    #clear_all_rows()
    #reset_transform_stage()
    