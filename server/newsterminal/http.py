"""
Fetching, and the cache that sits in front of it.

STDLIB ONLY. The whole service depends on fastapi, uvicorn and tzdata; the
fetching, XML parsing and JSON handling are all standard library. That is not
asceticism — it means a cold clone installs in seconds and there is no
transitive dependency between this terminal and a package that could vanish.

EVERY FETCH IS ALLOWED TO FAIL. `fetch` returns a FetchResult rather than
raising, and the result carries the reason. One dead publisher must cost one
row on the wire, never the terminal, and the panel that is missing has to be
able to say WHY it is missing rather than rendering an empty box.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from typing import Any

from .config import CACHE_DIR, UA


@dataclass
class FetchResult:
    """What one upstream gave us, including the ways it did not."""

    ok: bool
    body: bytes | None
    #: "live" on a successful fetch, "cache" when served from a fresh cache
    #: entry, "stale" when the fetch failed and a stale copy was used instead.
    source: str
    #: Age of the bytes in minutes — of the CACHE ENTRY, not the publication.
    age_min: float | None
    error: str | None
    status: int | None = None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace") if self.body else ""

    def json(self) -> Any:
        return json.loads(self.text) if self.body else None


class DiskCache:
    """One file per key. Nothing is committed until the caller has parsed it.

    Deliberately the same shape as GEXYGEN's `_DiskCache`, because the property
    that matters is the same: a write is `.tmp` then `os.replace`, so a process
    killed mid-write leaves the previous good copy rather than a truncated file
    that parses to nonsense on the next start.
    """

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def path(self, key: str) -> str:
        return os.path.join(self.root, re.sub(r"[^A-Za-z0-9_.-]", "_", key))

    def age_sec(self, key: str) -> float | None:
        p = self.path(key)
        return time.time() - os.path.getmtime(p) if os.path.exists(p) else None

    def read(self, key: str) -> bytes | None:
        p = self.path(key)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "rb") as f:
                return f.read()
        except OSError:
            return None

    def write(self, key: str, blob: bytes) -> None:
        p = self.path(key)
        tmp = p + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, p)
        except OSError:
            # A cache that cannot be written is a slower terminal, not a broken
            # one. Never let it take down the fetch that just succeeded.
            pass


CACHE = DiskCache(CACHE_DIR)


def _decompress(raw: bytes, encoding: str) -> bytes:
    """Some publishers ignore our Accept-Encoding and gzip anyway."""
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def fetch(
    url: str,
    *,
    key: str | None = None,
    ttl_sec: float = 300.0,
    timeout: int = 20,
    ua: str = UA,
    headers: dict[str, str] | None = None,
    stale_ok: bool = True,
) -> FetchResult:
    """GET a URL through the disk cache, and never raise.

    `ttl_sec` is how long a cached copy is served without going upstream at
    all. On a failed fetch the stale copy is served instead when `stale_ok`,
    and the result says `source="stale"` so the UI can label it — serving old
    bytes silently as though they were new is the one failure that would make
    this terminal worse than no terminal.
    """
    k = key or url
    age = CACHE.age_sec(k)
    if age is not None and age < ttl_sec:
        blob = CACHE.read(k)
        if blob is not None:
            return FetchResult(True, blob, "cache", age / 60.0, None)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            body = _decompress(raw, (r.headers.get("Content-Encoding") or "").lower())
            status = getattr(r, "status", 200)
        CACHE.write(k, body)
        return FetchResult(True, body, "live", 0.0, None, status)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as e:
        # BLE is deliberate here and nowhere else: this function's entire
        # contract is that an upstream cannot take the process down, and the
        # set of exceptions urllib raises through a proxy is not enumerable.
        reason = getattr(e, "reason", None)
        code = getattr(e, "code", None)
        msg = f"HTTP {code}" if code else str(reason or e) or e.__class__.__name__
        if stale_ok:
            blob = CACHE.read(k)
            if blob is not None:
                return FetchResult(True, blob, "stale", (age or 0) / 60.0, msg, code)
        return FetchResult(False, None, "unavailable", None, msg, code)


# ---------------------------------------------------------------------------
# XML / RSS
#
# Regex rather than ElementTree, and for one concrete reason: a meaningful
# fraction of publisher RSS in the wild is not well-formed (unescaped
# ampersands, stray control bytes, a CDATA block closed twice). ElementTree
# rejects the whole document; these give up on the one item that is broken and
# keep the other twenty-four. GEXYGEN's headlines.py made the same call.
# ---------------------------------------------------------------------------

_ITEM = re.compile(r"<item[\s>].*?</item>|<entry[\s>].*?</entry>", re.S | re.I)
_TAG_CACHE: dict[str, re.Pattern[str]] = {}


def _tag(block: str, name: str) -> str:
    p = _TAG_CACHE.get(name)
    if p is None:
        p = re.compile(rf"<{name}[^>]*>(.*?)</{name}>", re.S | re.I)
        _TAG_CACHE[name] = p
    m = p.search(block)
    return m.group(1).strip() if m else ""


_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
    "&#39;": "'", "&#x27;": "'", "&nbsp;": " ", "&mdash;": "—", "&ndash;": "–",
    "&hellip;": "…", "&rsquo;": "’", "&lsquo;": "‘", "&ldquo;": "“", "&rdquo;": "”",
}


# Mojibake: UTF-8 bytes that were decoded as cp1252 somewhere upstream and then
# re-encoded as UTF-8, so a right single quote (U+2019, bytes E2 80 99) arrives
# as the three characters "â€™". Roughly a quarter of the tape had it.
_MOJI = re.compile(r"[âÂÃ][-¿–—‘’“”€™œ]")


def _demojibake(s: str) -> str:
    """Undo a cp1252/UTF-8 double-encode, but only when it really is one.

    THE STRICT ROUND TRIP IS THE SAFETY. Re-encoding to cp1252 fails outright on
    any character that codec cannot represent, and the UTF-8 decode fails on any
    byte sequence that is not valid UTF-8 — so a string that merely happens to
    contain "â" (a French word, a name) throws and is returned untouched. Only a
    string that is genuinely the mojibake of valid UTF-8 survives both steps.
    """
    if not _MOJI.search(s):
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def clean_text(s: str) -> str:
    """Markup and entities out, one line of readable prose back."""
    s = _CDATA.sub(r"\1", s)
    s = _TAGS.sub(" ", s)
    for a, b in _ENTITIES.items():
        s = s.replace(a, b)
    # Numeric entities the table above does not name.
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    s = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
    # A SECOND TAG PASS, because the entity pass above can create tags.
    #
    # Several feeds double-escape their markup, so the description arrives as
    # `&lt;a href="http://…"&gt;`. The first `_TAGS` pass sees no angle brackets
    # and does nothing; the entity pass then turns them into real ones, and the
    # markup lands on the tape as visible text — a Guardian summary was ending
    # mid-attribute with `<a href="http` on screen.
    s = _TAGS.sub(" ", s)
    # AFTER the entity pass, not before: a feed can encode the mojibake itself
    # as entities (`&acirc;&#8364;&#8482;`), and those have to become characters
    # before the round trip can recognise them.
    s = _demojibake(s)
    return _WS.sub(" ", s).strip()


def rss_items(xml: str, limit: int = 60) -> list[dict[str, str]]:
    """RSS <item> and Atom <entry> alike → title/link/date/summary. Pure."""
    out: list[dict[str, str]] = []
    for m in _ITEM.finditer(xml):
        block = m.group(0)
        link = _tag(block, "link")
        if not link:
            # Atom puts the URL in an attribute rather than the element body.
            a = re.search(r'<link[^>]*href="([^"]+)"', block, re.I)
            link = a.group(1) if a else ""
        out.append(
            {
                "title": clean_text(_tag(block, "title")),
                "link": clean_text(link),
                "date": clean_text(
                    _tag(block, "pubDate") or _tag(block, "published") or _tag(block, "updated")
                ),
                "summary": clean_text(
                    _tag(block, "description") or _tag(block, "summary") or ""
                )[:400],
            }
        )
        if len(out) >= limit:
            break
    return out


@dataclass
class SourceStatus:
    """One upstream's health, carried to the UI so a hole can name itself."""

    name: str
    ok: bool = False
    items: int = 0
    source: str = "unavailable"
    age_min: float | None = None
    error: str | None = None
    last_ok_utc: str | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "items": self.items,
            "source": self.source,
            "age_min": round(self.age_min, 2) if self.age_min is not None else None,
            "error": self.error,
            "last_ok_utc": self.last_ok_utc,
            "notes": self.notes,
        }
