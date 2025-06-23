![Greenvest logo](greenvest.png)
# GreenVest Proxy (Proof of Concept)

**Status: Proof of Concept (PoC)**

GreenVest is a lightweight, asynchronous HTTP proxy built in Python. It’s designed to filter traffic based on URL reputation—**for HTTP endpoints only**—and includes two main components: a Proxy Server and a Reputation Service.

> ⚠️ **Note:** This is a Proof of Concept. It's **not** production-ready. Use it for learning, research, or experimentation—not for anything sensitive or critical.

---

## Why This Exists

GreenVest was created to support **security research and hands-on learning** around content filtering features in Proxy products. It demonstrates how a proxy can assess and allow or block HTTP requests based on the reputation of the target URL—similar to how enterprise security gateways work, but without the complexity or closed-source limitations.

By pairing it with a simple, separate reputation scoring service, GreenVest gives researchers and developers insight into how these decisions might be made, how misconfigurations can arise, or even how such systems might be abused (e.g., for data exfiltration). 

---

## What It Includes

GreenVest is made up of two Python-based components:

### 1. **Proxy Server (`proxy_server.py`)**

Handles client HTTP requests, authenticates users, queries the reputation service, and either blocks or forwards the traffic.

- **Tech stack**:
  - Python 3.7+
  - `asyncio` for async I/O
  - `aiohttp` for HTTP handling
  - Optional TLS support using `ssl`

### 2. **Reputation Service (`reputation_service.py`)**

A simple dummy scoring engine for URLs based on keywords. It fetches content, looks for the keywords in the content it fetches, and returns a reputation score. It also uses SQLite to cache results.

- **Tech stack**:
  - Python 3.7+
  - `aiohttp` (server + client)
  - `aiosqlite` for caching

---

## What It Can Do (Right Now)

- Forward HTTP requests
- Score and block URLs using the reputation service
- Support basic auth (username:password)
- Optionally run with TLS (client-to-proxy)

---

## How It Works

This is the behavior we have observed in a commercial product.

1. A client sends an HTTP request to the proxy
2. The proxy sends the target URL to the reputation service (with a 10s timeout)
3. The proxy authenticates the client
4. The service analyzes the URL and returns a score
5. If the client authenticated correctly 
  5.1. If the score is too high (bad), the proxy blocks it and returns an error page (403). 
  5.2  Otherwise, the request is forwarded (with a 30s timeout)
6. If the client didnt authenticate correctly, return auth request.

---

## Requirements

- Python 3.7 or newer
- Install dependencies:
  ```bash
  pip install aiohttp aiosqlite
  ```
- (Optional TLS) You’ll need OpenSSL or similar to generate `cert.pem` and `key.pem`

---

## Getting Started

### Step 1: Run the Reputation Service

Optional config in `reputation_service.py`:
- Set keywords: `KEYWORDS = ["bad", "words", ...]`
- Choose a cache DB name
- Set cache time-to-live (in days)

Start the service:
```bash
python3 reputation_service.py [--host 0.0.0.0] [--port 8081] [--debug]
```

### Step 2: Run the Proxy Server

Edit `proxy_server.py` to configure:
- Auth users: `AUTH_USERS = ["user:pass", ...]`
- Blocking threshold: `BLOCK_THRESHOLD = 0.3`

(Optional TLS setup):
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Start the proxy:
```bash
python3 proxy_server.py --reputation-service "http://localhost:8081/reputation" 
```

Other options:
- `--port` (default: 8443)
- `--host` (default: 0.0.0.0)
- `--debug` for verbose logging
- `-a` / `--printanswersfromreputation` to log reputation snippets

### Step 3: Client Setup

curl -x http://127.0.0.1:8999 http://httpbin.org/ss

---

## Important Limitations

- **HTTP only**: No HTTPS or `CONNECT` method support. Encrypted traffic can't be inspected.
- **Insecure Auth**:
  - Credentials are hardcoded.
  - Basic auth is only secure if used over TLS.
- **Hardcoded settings**: All config is in the Python files.
- **Naive reputation scoring**: Basic keyword match—easy to trick.
- **Weak error handling**: Needs much better exception logic.
- **No input validation**: Assumes valid URLs.
- **Simple logging**: Just print statements—no logging framework.

---

## Reporting Issues

This is an experimental project. There’s no official support, but if you run into issues during research or testing, feel free to open an issue.

---

## Contributing

This is a Proof of Concept for educational use only and is not accepting contributions at this time.

---

## Author

Jose Garduno
https://www.linkedin.com/in/josegarduno/
