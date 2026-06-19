"""
Test suite for Competitor Website Change Monitor MCP Server
Run with:  pytest tests/ -v
"""

import asyncio
import json
import os
import pytest

# Point cache at a temp file so tests never touch production data
os.environ["MONITOR_CACHE_FILE"] = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "pytest_monitor_cache.json")

from server import (
    extract_key_data,
    diff_data,
    hash_data,
    load_cache,
    save_cache,
    call_tool,
    CACHE_FILE,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_HTML_V1 = """
<html>
<head><title>BestShop — Running Shoes</title></head>
<body>
  <h2 class="product-name">Nike Air Max 90</h2>
  <h2 class="product-name">Adidas Ultraboost 22</h2>
  <span class="price">$120.00</span>
  <span class="price">$180.00</span>
  <span class="discount">20% OFF today!</span>
</body></html>
"""

MOCK_HTML_V2 = """
<html>
<head><title>BestShop — Running Shoes SALE</title></head>
<body>
  <h2 class="product-name">Nike Air Max 90</h2>
  <h2 class="product-name">Adidas Ultraboost 22</h2>
  <h2 class="product-name">New Balance 990v5</h2>
  <span class="price">$99.00</span>
  <span class="price">$180.00</span>
  <span class="discount">30% OFF sitewide!</span>
</body></html>
"""

FAKE_URL = "https://bestshop-fake.example.com/shoes"


@pytest.fixture(autouse=True)
def clean_cache():
    """Wipe cache before every test."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    yield
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


# ── Unit Tests: extraction ────────────────────────────────────────────────────

class TestExtraction:
    def test_extracts_prices(self):
        data = extract_key_data(MOCK_HTML_V1)
        assert "$120.00" in data["prices"]
        assert "$180.00" in data["prices"]

    def test_extracts_products(self):
        data = extract_key_data(MOCK_HTML_V1)
        assert "Nike Air Max 90" in data["products"]
        assert "Adidas Ultraboost 22" in data["products"]

    def test_extracts_promotions(self):
        data = extract_key_data(MOCK_HTML_V1)
        assert "20% OFF today!" in data["promotions"]

    def test_extracts_title(self):
        data = extract_key_data(MOCK_HTML_V1)
        assert data["title"] == "BestShop — Running Shoes"

    def test_empty_html_returns_empty_fields(self):
        data = extract_key_data("<html><body></body></html>")
        assert data["prices"] == []
        assert data["products"] == []
        assert data["promotions"] == []


# ── Unit Tests: hashing ───────────────────────────────────────────────────────

class TestHashing:
    def test_hash_is_stable(self):
        data = extract_key_data(MOCK_HTML_V1)
        assert hash_data(data) == hash_data(data)

    def test_different_data_gives_different_hash(self):
        d1 = extract_key_data(MOCK_HTML_V1)
        d2 = extract_key_data(MOCK_HTML_V2)
        assert hash_data(d1) != hash_data(d2)

    def test_hash_is_md5_string(self):
        data = extract_key_data(MOCK_HTML_V1)
        h = hash_data(data)
        assert isinstance(h, str)
        assert len(h) == 32


# ── Unit Tests: diff ─────────────────────────────────────────────────────────

class TestDiff:
    def test_detects_price_change(self):
        d1, d2 = extract_key_data(MOCK_HTML_V1), extract_key_data(MOCK_HTML_V2)
        changes = diff_data(d1, d2)
        types = {c["type"] for c in changes}
        assert "price_change" in types

    def test_detects_new_product(self):
        d1, d2 = extract_key_data(MOCK_HTML_V1), extract_key_data(MOCK_HTML_V2)
        changes = diff_data(d1, d2)
        new_prod = next(c for c in changes if c["type"] == "new_products")
        assert "New Balance 990v5" in new_prod["items"]

    def test_detects_promotion_change(self):
        d1, d2 = extract_key_data(MOCK_HTML_V1), extract_key_data(MOCK_HTML_V2)
        types = {c["type"] for c in diff_data(d1, d2)}
        assert "promotion_change" in types

    def test_detects_title_change(self):
        d1, d2 = extract_key_data(MOCK_HTML_V1), extract_key_data(MOCK_HTML_V2)
        types = {c["type"] for c in diff_data(d1, d2)}
        assert "title_change" in types

    def test_no_changes_when_identical(self):
        d1 = extract_key_data(MOCK_HTML_V1)
        assert diff_data(d1, d1) == []

    def test_detects_removed_product(self):
        d1, d2 = extract_key_data(MOCK_HTML_V2), extract_key_data(MOCK_HTML_V1)
        types = {c["type"] for c in diff_data(d1, d2)}
        assert "removed_products" in types


# ── Integration Tests: MCP tools ─────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestMCPTools:
    def _inject_cache(self, url, data):
        cache = {url: {"hash": hash_data(data), "data": data, "last_check": "2026-01-01T00:00:00"}}
        save_cache(cache)

    def _parse(self, result):
        return json.loads(result[0].text)

    def test_list_when_empty(self):
        result = run(call_tool("list_monitored_websites", {}))
        assert "No websites monitored yet" in result[0].text

    def test_snapshot_when_not_tracked(self):
        result = run(call_tool("get_website_snapshot", {"url": FAKE_URL}))
        assert "No snapshot" in result[0].text

    def test_remove_untracked_url(self):
        result = run(call_tool("remove_website", {"url": FAKE_URL}))
        assert "not being monitored" in result[0].text

    def test_snapshot_returns_cached_data(self):
        data = extract_key_data(MOCK_HTML_V1)
        self._inject_cache(FAKE_URL, data)
        result = self._parse(run(call_tool("get_website_snapshot", {"url": FAKE_URL})))
        assert result["data"]["title"] == "BestShop — Running Shoes"

    def test_remove_tracked_url(self):
        data = extract_key_data(MOCK_HTML_V1)
        self._inject_cache(FAKE_URL, data)
        result = run(call_tool("remove_website", {"url": FAKE_URL}))
        assert "Removed" in result[0].text
        # Cache should now be empty
        assert load_cache() == {}

    def test_list_shows_tracked_urls(self):
        data = extract_key_data(MOCK_HTML_V1)
        self._inject_cache(FAKE_URL, data)
        result = self._parse(run(call_tool("list_monitored_websites", {})))
        assert isinstance(result, list)
        assert result[0]["url"] == FAKE_URL

    def test_change_detection_via_cache_mutation(self):
        """Inject old state, mutate hash to force diff, verify change detected."""
        old_data = extract_key_data(MOCK_HTML_V1)
        # Save with a fake/wrong hash so next check sees a "change"
        cache = {FAKE_URL: {"hash": "old_fake_hash", "data": old_data, "last_check": "2026-01-01"}}
        save_cache(cache)

        # The new data is v2 — but we test diff_data directly (no network)
        new_data = extract_key_data(MOCK_HTML_V2)
        changes = diff_data(old_data, new_data)
        types = {c["type"] for c in changes}

        assert "price_change" in types
        assert "new_products" in types
        assert "promotion_change" in types
        assert "title_change" in types

    def test_unknown_tool_returns_error(self):
        result = run(call_tool("nonexistent_tool", {}))
        assert "Unknown tool" in result[0].text