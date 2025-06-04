#!/usr/bin/env python3
"""
reputation_service.py – Keyword-based reputation service with SQLite caching
"""

from aiohttp import web
import aiohttp
import aiosqlite
import asyncio
import time
from datetime import datetime, timedelta

KEYWORDS = ["sex", "roblox", "hack", "phish"]
CACHE_DB = "reputation.db"
CACHE_TTL_DAYS = 7
SNIPPET_LEN = 500
DEBUG = False

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def debug_log(msg):
    if DEBUG:
        log(f"[DEBUG] {msg}")

async def init_db():
    async with aiosqlite.connect(CACHE_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reputation (
                url TEXT PRIMARY KEY,
                date_checked TEXT,
                score REAL,
                snippet TEXT
            )
        """)
        await db.commit()

async def cache_lookup(url):
    async with aiosqlite.connect(CACHE_DB) as db:
        async with db.execute("SELECT date_checked, score, snippet FROM reputation WHERE url = ?", (url,)) as cur:
            row = await cur.fetchone()
            if row:
                date_checked = datetime.fromisoformat(row[0])
                if datetime.utcnow() - date_checked < timedelta(days=CACHE_TTL_DAYS):
                    debug_log(f"Cache HIT for {url}")
                    return {"score": row[1], "snippet": row[2], "cached": True}
    debug_log(f"Cache MISS for {url}")
    return None

async def cache_store(url, score, snippet):
    async with aiosqlite.connect(CACHE_DB) as db:
        await db.execute(
            "REPLACE INTO reputation (url, date_checked, score, snippet) VALUES (?, ?, ?, ?)",
            (url, datetime.utcnow().isoformat(), score, snippet)
        )
        await db.commit()
        debug_log(f"Stored reputation result for {url}")

async def analyze_url(url):
    cached = await cache_lookup(url)
    if cached:
        return cached

    score = 0.1
    snippet = ""
    try:
        debug_log(f"Fetching URL: {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                async for chunk in resp.content.iter_chunked(512):
                    text = chunk.decode(errors="ignore")
                    snippet += text
                    if any(kw in text.lower() for kw in KEYWORDS):
                        score = 0.9
                        break
                    if len(snippet) >= SNIPPET_LEN:
                        break
        snippet = snippet[:SNIPPET_LEN]
    except Exception as e:
        log(f"Fetch error for {url}: {e}")
        score = 1.0
        snippet = "Fetch failed"

    await cache_store(url, score, snippet)
    return {"score": score, "snippet": snippet, "cached": False}

async def handle_reputation(request):
    url = request.query.get("url")
    if not url:
        return web.json_response({"error": "Missing 'url' param"}, status=400)

    log(f"Incoming reputation check: {url}")
    result = await analyze_url(url)
    return web.json_response({
        "url": url,
        "score": result["score"],
        "snippet": result["snippet"],
        "cached": result["cached"]
    })

def main():
    import argparse
    global DEBUG

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    DEBUG = args.debug

    app = web.Application()
    app.router.add_get("/reputation", handle_reputation)

    log(f"Starting reputation service at http://{args.host}:{args.port}")
    if DEBUG:
        print("Debug logging ENABLED")
    asyncio.run(init_db())
    web.run_app(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
