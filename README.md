# 🔍 Competitor Website Change Monitor — MCP Server

[![MCPize](https://mcpize.com/badge/@300joh/competitor-monitor)](https://mcpize.com/mcp/competitor-monitor)

Monitor competitor websites for **price drops, new products, promotions, and content changes** — directly from Claude, Cursor, or any MCP-compatible AI client.

---

## What It Detects

| Change | Example |
|---|---|
| 💰 Price change | `$120 → $99` |
| 🆕 New product | `"New Balance 990v5" appeared` |
| 🗑️ Removed product | `"Old SKU" no longer listed` |
| 🎯 Promotion | `"20% OFF" → "30% OFF sitewide"` |
| 📄 Page title | `"BestShop Shoes" → "BestShop SALE"` |

---

## Quickstart (Local / Claude Desktop)

```bash
# 1. Clone
git clone https://github.com/Oko300/competitor-monitor-mcp
cd competitor-monitor-mcp

# 2. Install
pip install -r requirements.txt

# 3. Test
pytest tests/ -v

# 4. Add to Claude Desktop
#    Edit: ~/Library/Application Support/Claude/claude_desktop_config.json  (Mac)
#    Edit: %APPDATA%\Claude\claude_desktop_config.json                       (Windows)
```

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "competitor-monitor": {
      "command": "python3",
      "args": ["C:/path/to/server.py"],
      "env": {
        "MONITOR_CACHE_FILE": "C:/path/to/monitor_cache.json"
      }
    }
  }
}
```

## Connect via MCPize

Use this MCP server instantly with no local installation:

```bash
npx -y mcpize connect @300joh/competitor-monitor --client claude
```

Or connect at: **https://mcpize.com/mcp/competitor-monitor**
---

## MCP Tools Available

| Tool | What it does |
|---|---|
| `monitor_website` | Check one URL for changes |
| `monitor_multiple_websites` | Check a batch of URLs at once |
| `list_monitored_websites` | See all tracked URLs |
| `get_website_snapshot` | View last cached data (no re-fetch) |
| `remove_website` | Stop tracking a URL |

---

## Example Output

```json
{
  "url": "https://competitor.com/shoes",
  "changed": true,
  "changes": [
    {
      "type": "price_change",
      "removed": ["$120.00"],
      "added": ["$99.00"],
      "timestamp": "2026-06-19T10:00:00"
    },
    {
      "type": "new_products",
      "items": ["New Balance 990v5"],
      "timestamp": "2026-06-19T10:00:00"
    }
  ]
}
```

---

## Project Structure

```
competitor-monitor-mcp/
├── server.py                  ← MCP server (main product)
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── README.md
├── tests/
│   └── test_server.py         ← 13 pytest tests
└── .vscode/
    ├── launch.json            ← Run/debug configs
    └── extensions.json        ← Recommended extensions
```

---

## Pricing Tiers (MCPize)

| Plan | Sites | Frequency | Price |
|---|---|---|---|
| Starter | 5 | Daily | $9.99/mo |
| Pro | 25 | Hourly | $29.99/mo |
| Business | 100 | Real-time | $79.99/mo |

---

## Notes

- Works on standard HTML sites (Shopify, WooCommerce, static pages)
- JavaScript-heavy SPAs may need a headless browser (Playwright) upgrade
- Cache persists across restarts via `monitor_cache.json`
- 100% free: no third-party APIs, no paid data sources