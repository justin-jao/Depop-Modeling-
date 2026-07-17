"""
Thin wrapper around eBay's OAuth token endpoint and Browse API.

All calls in this file happen server-side only. The Client ID / Client
Secret and the resulting access token never get sent to the browser -
the Flask app in app.py is the only thing that talks to this module.
"""

import base64
import os
import time

import requests

EBAY_ENV = os.environ.get("EBAY_ENV", "PRODUCTION").upper()  # PRODUCTION or SANDBOX

if EBAY_ENV == "SANDBOX":
    OAUTH_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.sandbox.ebay.com/buy/browse/v1"
else:
    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"

CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

# In-memory token cache. One process = one shared application token for
# every visitor hitting this backend. This is what makes eBay's daily
# call limit a *shared* pool across all your users (see chat notes).
_token_cache = {"access_token": None, "expires_at": 0}


class EbayAuthError(RuntimeError):
    pass


def _get_app_token() -> str:
    """Return a cached Application access token, refreshing if it's
    expired or about to expire (60s safety margin)."""
    if _token_cache["access_token"] and _token_cache["expires_at"] - 60 > time.time():
        return _token_cache["access_token"]

    if not CLIENT_ID or not CLIENT_SECRET:
        raise EbayAuthError(
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set. "
            "Copy .env.example to .env and fill in your keys."
        )

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
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
    if resp.status_code != 200:
        raise EbayAuthError(f"eBay OAuth failed ({resp.status_code}): {resp.text}")

    payload = resp.json()
    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = time.time() + int(payload.get("expires_in", 7200))
    return _token_cache["access_token"]


def _headers():
    return {
        "Authorization": f"Bearer {_get_app_token()}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        "Accept": "application/json",
    }


def search_items(query: str, limit: int = 20):
    """Keyword search -> list of item summaries (lightweight, no full
    description/creation date yet)."""
    resp = requests.get(
        f"{BROWSE_BASE}/item_summary/search",
        headers=_headers(),
        params={"q": query, "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("itemSummaries", [])


def get_item(item_id: str):
    """Full item detail, including itemCreationDate, description,
    condition, item specifics (aspects), category path, and location."""
    resp = requests.get(
        f"{BROWSE_BASE}/item/{item_id}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_item_by_legacy_id(legacy_item_id: str):
    """Same full item detail as get_item(), but looked up by the
    numeric ID that appears in a normal ebay.com/itm/... URL, rather
    than the RESTful itemId eBay uses internally."""
    resp = requests.get(
        f"{BROWSE_BASE}/item/get_item_by_legacy_id",
        headers=_headers(),
        params={"legacy_item_id": legacy_item_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
