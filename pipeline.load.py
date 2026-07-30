import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

def load_crawlee_data(dataset_path: str, search_query: str, db_path: str = "depop_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Generate a unique Run ID
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc).isoformat()

    dataset_dir = Path(dataset_path)
    if not dataset_dir.exists():
        print(f"Dataset directory not found: {dataset_dir}")
        return

    # Create the run record
    cursor.execute("""
        INSERT INTO scrape_runs (run_id, search_query, start_time)
        VALUES (?, ?, ?)
    """, (run_id, search_query, start_time))

    files_processed = 0

    # Iterate over Crawlee's JSON output
    for json_file in dataset_dir.glob("*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            record = json.load(f)

        source_url = record.get("source_url")
        api_payload = record.get("api_payload")

        if source_url and api_payload:
            cursor.execute("""
                INSERT INTO raw_listings (run_id, source_url, api_payload)
                VALUES (?, ?, ?)
            """, (run_id, source_url, json.dumps(api_payload)))
            files_processed += 1

    # Update the run with completion stats
    finish_time = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        UPDATE scrape_runs 
        SET finish_time = ?, listing_count = ? 
        WHERE run_id = ?
    """, (finish_time, files_processed, run_id))

    conn.commit()
    conn.close()
    print(f"Loaded {files_processed} raw files into run {run_id}.")

if __name__ == "__main__":
    dataset_path = r"storage/datasets/default"
    
    # TODO: example search query for scraper run metadata, 
    # need to change this later for one step ingestion, TAKE QUERY FROM depop.scrape.py
    query = "black pants" 
    
    load_crawlee_data(dataset_path, query)