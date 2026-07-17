"""
Cached, hashing HTTP fetcher for the ingestion pipeline.

Every fetched body is stored content-addressed under pipeline/data/raw/ and
recorded in an index (url -> sha256, fetched_at, size). Immutable resources
(release blobs, per-vote XLSX files) are served from the cache on re-runs, so
nightly cron runs only download what is new. The SHA-256 is the provenance
hash that ends up on every evidence item.
"""
import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Tuple

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
RAW_DIR = os.path.join(DATA_DIR, "raw")
INDEX_PATH = os.path.join(RAW_DIR, "index.json")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WahlkompassIngest/1.0"


def _load_index() -> dict:
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_index(index: dict) -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    tmp = INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, INDEX_PATH)


def _blob_path(sha256: str) -> str:
    return os.path.join(RAW_DIR, sha256[:2], sha256)


def fetch(url: str, cache: bool = True, headers: Optional[dict] = None,
          throttle_seconds: float = 0.0) -> Tuple[bytes, str]:
    """
    Fetch url, return (body, sha256). With cache=True a previously fetched url
    is served from disk without a network call. throttle_seconds sleeps before
    an actual network request (rate-limited APIs), never before a cache hit.
    """
    index = _load_index()
    if cache and url in index:
        path = _blob_path(index[url]["sha256"])
        if os.path.exists(path):
            with open(path, "rb") as f:
                body = f.read()
            return body, index[url]["sha256"]

    if throttle_seconds > 0:
        time.sleep(throttle_seconds)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()

    sha256 = hashlib.sha256(body).hexdigest()
    path = _blob_path(sha256)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(body)

    index = _load_index()
    index[url] = {
        "sha256": sha256,
        "size": len(body),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_index(index)
    return body, sha256


def load_env(path: Optional[str] = None) -> dict:
    """Minimal .env reader (KEY=VALUE lines, # comments). No dependency."""
    if path is None:
        path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env
