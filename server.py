"""
Competitor Website Price & Product Change Monitor — MCP Server
Compatible with: Claude Desktop, Cursor, MCPize
"""

import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Persistent cache (survives restarts) ────────────────────────────────────
CACHE_FILE = Path(os.environ.get("MONITOR_CACHE_FILE", "monitor_cache.json"))


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ── Fetch ────────────────────────────────────────────────────────────────────

async def fetch_website(url: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return None


# ── Extract ──────────────────────────────────────────────────────────────────

def extract_key_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "footer", "nav"]):
        tag.decompose()

    price_classes = ["price", "Price", "product-price", "price-tag",
                     "current-price", "offer-price", "sale-price"]
    prices = set()
    for cls in price_classes:
        for el in soup.find_all(["span", "div", "p", "strong"], class_=cls):
            text = el.get_text(strip=True)
            if any(sym in text for sym in ["$", "€", "£", "₦", "₹", "¥"]):
                prices.add(text[:50])

    product_classes = ["product-name", "product-title", "product__title",
                       "item-name", "woocommerce-loop-product__title"]
    products = set()
    for cls in product_classes:
        for el in soup.find_all(["h1", "h2", "h3", "span", "a"], class_=cls):
            text = el.get_text(strip=True)
            if 3 < len(text) < 150:
                products.add(text)

    promo_classes = ["promo", "promotion", "discount", "sale", "offer",
                     "deal", "special", "badge", "label-sale"]
    promotions = set()
    for cls in promo_classes:
        for el in soup.find_all(["div", "span", "p", "strong"], class_=cls):
            text = el.get_text(strip=True)
            if 5 < len(text) < 200:
                promotions.add(text)

    title_tag = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else ""

    return {
        "prices":     sorted(prices),
        "products":   sorted(list(products)[:30]),
        "promotions": sorted(promotions),
        "title":      page_title,
    }


# ── Hash & Diff ──────────────────────────────────────────────────────────────

def hash_data(data: dict) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def diff_data(old: dict, new: dict) -> list[dict]:
    changes = []
    now = datetime.now().isoformat()

    for field, label in [("prices", "price_change"), ("promotions", "promotion_change")]:
        old_set, new_set = set(old[field]), set(new[field])
        if old_set != new_set:
            changes.append({
                "type":      label,
                "removed":   sorted(old_set - new_set),
                "added":     sorted(new_set - old_set),
                "timestamp": now,
            })

    old_p, new_p = set(old["products"]), set(new["products"])
    if new_p - old_p:
        changes.append({"type": "new_products",     "items": sorted(new_p - old_p)[:10], "timestamp": now})
    if old_p - new_p:
        changes.append({"type": "removed_products", "items": sorted(old_p - new_p)[:10], "timestamp": now})

    if old["title"] != new["title"]:
        changes.append({"type": "title_change", "old": old["title"], "new": new["title"], "timestamp": now})

    return changes


# ── Core check ───────────────────────────────────────────────────────────────

async def check_url(url: str, cache: dict) -> dict:
    html = await fetch_website(url)
    if not html:
        return {"url": url, "error": "Failed to fetch — check URL or network"}

    data    = extract_key_data(html)
    current = hash_data(data)
    prev    = cache.get(url)
    changes = diff_data(prev["data"], data) if prev and prev["hash"] != current else []

    cache[url] = {
        "hash":       current,
        "data":       data,
        "last_check": datetime.now().isoformat(),
    }
    save_cache(cache)

    return {
        "url":          url,
        "changed":      bool(changes),
        "changes":      changes,
        "last_check":   cache[url]["last_check"],
        "current_data": data,
        "first_check":  prev is None,
    }


# ── MCP Server ───────────────────────────────────────────────────────────────

app = Server("competitor-monitor")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="monitor_website",
            description="Check a single competitor website for price, product, or promotion changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to monitor"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="monitor_multiple_websites",
            description="Check multiple competitor websites in one call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of URLs to monitor",
                    }
                },
                "required": ["urls"],
            },
        ),
        Tool(
            name="list_monitored_websites",
            description="List all websites currently being tracked with their last-check time.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="remove_website",
            description="Stop monitoring a website and remove it from the cache.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to remove"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="get_website_snapshot",
            description="Return the last cached snapshot for a URL without re-fetching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to inspect"}
                },
                "required": ["url"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    cache = load_cache()

    if name == "monitor_website":
        result = await check_url(arguments["url"], cache)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "monitor_multiple_websites":
        results = await asyncio.gather(*[check_url(u, cache) for u in arguments["urls"]])
        summary = {
            "total":   len(results),
            "changed": sum(1 for r in results if r.get("changed")),
            "results": list(results),
        }
        return [TextContent(type="text", text=json.dumps(summary, indent=2))]

    elif name == "list_monitored_websites":
        if not cache:
            return [TextContent(type="text", text="No websites monitored yet.")]
        rows = [
            {"url": url, "last_check": e["last_check"], "title": e["data"].get("title", "")}
            for url, e in cache.items()
        ]
        return [TextContent(type="text", text=json.dumps(rows, indent=2))]

    elif name == "remove_website":
        url = arguments["url"]
        if url in cache:
            del cache[url]
            save_cache(cache)
            return [TextContent(type="text", text=f"Removed {url} from monitoring.")]
        return [TextContent(type="text", text=f"{url} was not being monitored.")]

    elif name == "get_website_snapshot":
        url   = arguments["url"]
        entry = cache.get(url)
        if not entry:
            return [TextContent(type="text", text=f"No snapshot for {url}. Run monitor_website first.")]
        return [TextContent(type="text", text=json.dumps(entry, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())