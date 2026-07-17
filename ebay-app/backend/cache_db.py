"""
Small SQLite cache for mapped listing rows.

Why this exists: the eBay Browse API rate limit applies to your whole
application, shared across every visitor to your frontend. If ten
people search "vintage levis" in the same hour, you want one eBay call
per unique item, not ten. This cache stores the mapped 8-field rows
keyed by item_id, along with a fetched_at timestamp, and serves from
cache when the entry is still "fresh" (see CACHE_TTL_SECONDS).

SCHEMA_VERSION: bump this any time map_item() in app.py changes which
fields it returns (e.g. adding "price"). Rows written under an older
version are treated as a cache miss, so they get re-fetched from eBay
with the current mapping instead of silently being served with the
old, incomplete shape.
"""

import json
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "listings_cache.db"

SCHEMA_VERSION = 2  # bumped when "price" / "price_note" were added

# How long a cached row is considered fresh before we re-fetch from eBay.
# eBay's API terms expect listing data to be refreshed periodically
# rather than served stale indefinitely - 6 hours is a reasonable
# default for browsing; tighten it if you show live price/availability.
CACHE_TTL_SECONDS = 6 * 60 * 60


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                item_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 0,
                fetched_at REAL NOT NULL
            )
            """
        )
        # Handles upgrading a DB created before schema_version existed.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(listings)")]
        if "schema_version" not in cols:
            conn.execute(
                "ALTER TABLE listings ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 0"
            )


def get_fresh(item_id: str):
    with _conn() as conn:
        row = conn.execute(
            "SELECT data, fetched_at, schema_version FROM listings WHERE item_id = ?",
            (item_id,),
        ).fetchone()
    if not row:
        return None
    if row["schema_version"] != SCHEMA_VERSION:
        return None  # mapping shape changed since this was cached - treat as a miss
    if time.time() - row["fetched_at"] > CACHE_TTL_SECONDS:
        return None
    return json.loads(row["data"])


def put(item_id: str, data: dict):
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO listings (item_id, data, schema_version, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                data = excluded.data,
                schema_version = excluded.schema_version,
                fetched_at = excluded.fetched_at
            """,
            (item_id, json.dumps(data), SCHEMA_VERSION, time.time()),
        )


def stats():
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM listings").fetchone()
    return {"cached_items": row["n"]}