#!/usr/bin/env python3
"""
proxy_server.py – TLS HTTP Proxy using external reputation service
"""

import argparse, asyncio, base64, ssl
from datetime import datetime
import aiohttp

AUTH_USERS = ["alice:secret", "bob:hunter2"]
BLOCK_THRESHOLD = 0.3
DEBUG = False

session: aiohttp.ClientSession = None
reputation_service_url: str = None

def log(event: str, **fields):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    details = " | ".join(f"{k}={v}" for k, v in fields.items())
    print(f"[{ts}] {event:<12} :: {details}")

def debug_log(msg):
    if DEBUG: print(f"[DEBUG] {msg}")

def check_credentials(encoded: str) -> tuple[bool, str]:
    try:
        creds = base64.b64decode(encoded).decode()
    except Exception:
        return False, "invalid"
    return creds in AUTH_USERS, creds

async def ask_reputation(url: str) -> dict:
    try:
        async with session.get(reputation_service_url, params={"url": url}, timeout=10) as resp:
            return await resp.json()
    except Exception as e:
        log("REPUTATION_ERR", error=str(e))
        return {"score": 1.0, "snippet": "Check failed", "cached": False}

async def fetch_upstream(method: str, url: str, headers: dict, body: bytes | None):
    async with session.request(method, url, headers=headers, data=body, timeout=30) as r:
        return r.status, dict(r.headers), await r.read()

BLOCK_PAGE = (
    "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
    "<h1>BLOCKED</h1><p>This URL is blocked by policy.</p>"
).encode()

UNAUTH_PAGE = (
    "HTTP/1.1 401 Unauthorized\r\nProxy-Authenticate: Basic realm=\"GreenVestProxy\"\r\nContent-Length: 0\r\n\r\n"
).encode()

async def handle_proxy(reader, writer, print_rep=False):
    try:
        raw_head = await reader.readuntil(b"\r\n\r\n")
        req_line, *hdr_lines = raw_head.decode("utf-8", "ignore").split("\r\n")
        method, url, _ = req_line.split(" ", 2)

        if method.upper() == "CONNECT":
            log("REJECT", reason="CONNECT not supported")
            writer.write(
                b"HTTP/1.1 405 Method Not Allowed\r\n"
                b"Content-Type: text/plain\r\nConnection: close\r\n\r\n"
                b"CONNECT not supported.\r\n"
            )
            await writer.drain()
            return

        headers = {}
        for line in hdr_lines:
            if line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        log("REQUEST", method=method, url=url)

        rep = await ask_reputation(url)
        log("REPUTATION", url=url, score=rep["score"], cached=rep.get("cached", False))
        if print_rep:
            print(f"[rep-body] {rep['snippet'][:100]!r}")

        auth_hdr = headers.get("proxy-authorization", "")
        auth_ok, user = False, "unknown"
        if auth_hdr.lower().startswith("basic "):
            auth_ok, user = check_credentials(auth_hdr.split(" ", 1)[1])
        log("AUTH", result="OK" if auth_ok else "FAIL", user=user)

        if not auth_ok:
            writer.write(UNAUTH_PAGE)
            await writer.drain()
            return

        if rep["score"] > BLOCK_THRESHOLD:
            writer.write(BLOCK_PAGE)
            await writer.drain()
            return

        for hop in ("proxy-authorization", "proxy-connection", "connection",
                    "keep-alive", "upgrade", "te", "trailers"):
            headers.pop(hop, None)

        status, up_hdrs, up_body = await fetch_upstream(method, url, headers, None)
        status_line = f"HTTP/1.1 {status} OK\r\n"
        up_hdrs.pop("Transfer-Encoding", None)
        up_hdrs["Content-Length"] = str(len(up_body))
        hdr_blob = "".join(f"{k}: {v}\r\n" for k, v in up_hdrs.items())

        writer.write(status_line.encode() + hdr_blob.encode() + b"\r\n" + up_body)
        await writer.drain()
        log("RESPONSE", action="proxied", code=status)

    except Exception as e:
        log("ERROR", message=repr(e))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except: pass

async def main(args):
    global session, reputation_service_url, DEBUG
    DEBUG = args.debug
    session = aiohttp.ClientSession()
    reputation_service_url = args.reputation_service

    ssl_ctx = None
    if args.tls:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain("cert.pem", "key.pem")

    print("\n=== Proxy Configuration ===")
    print(f"TLS Enabled           : {'YES' if args.tls else 'NO'}")
    print(f"Proxy Host            : {args.host}")
    print(f"Proxy Port            : {args.port}")
    print(f"Print Reputation Body : {'YES' if args.print_rep else 'NO'}")
    print(f"Reputation Service    : {reputation_service_url}")
    print(f"Debug Mode            : {'YES' if args.debug else 'NO'}")
    print("============================\n")

    handler = lambda r, w: asyncio.create_task(handle_proxy(r, w, args.print_rep))
    server = await asyncio.start_server(handler, host=args.host, port=args.port, ssl=ssl_ctx)
    print(f"Proxy running on {args.host}:{args.port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--printanswersfromreputation", dest="print_rep", action="store_true")
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--reputation-service", type=str, required=True)
    parser.add_argument("--debug", action="store_true")
    asyncio.run(main(parser.parse_args()))
