"""
Gamma levels — borrowed whole from GEXYGEN, never recomputed.

SEVEN NUMBERS PER ASSET AND NOT ONE MORE: three call walls, three put walls,
the gamma flip. That is the owner's instruction and it is also the right shape
for this terminal — GEXYGEN is where a gamma map is READ, with its strike
profile, its charm and vanna curves and its per-expiry book. What a news
terminal needs is the handful of prices that say where dealer hedging turns,
so a headline can be judged against them.

WHY NOT COMPUTE THEM HERE. Two engines that both turn an option chain into a
call wall will disagree the moment either is touched, and then there are two
call walls on two screens and no way to know which one is real. GEXYGEN already
ranks the top three the way its own chart indicator does; this reads that
ranking rather than inventing a second one. It is the same argument GEXYGEN's
own levels.txt docstring makes about the NinjaScript indicator, one level out.

SPOT COMES ALONG. Not as an eighth level but because three call walls above and
three put walls below are meaningless without knowing which are above and which
are below — the panel needs it to place price inside the structure at all.

DEGRADES TO NOTHING, LOUDLY. If GEXYGEN is not running this returns no levels
and says why. It must never fall back to a remembered set: a wall from an hour
ago drawn as though it were current is precisely the failure mode GEXYGEN's own
README calls the worst thing this kind of product can do.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from ..config import GEX_ASSETS, GEXYGEN_API, UA
from ..http import SourceStatus, fetch

# The only keys read out of levels.txt. Everything else the file carries —
# max pain, the ladder, the expected move — is deliberately dropped.
WANTED = {
    "FLIP": ("flip", "Gamma flip", "flip"),
    "CALL_WALL": ("call_1", "Call wall", "call"),
    "CALL_WALL_2": ("call_2", "Call wall 2", "call"),
    "CALL_WALL_3": ("call_3", "Call wall 3", "call"),
    "PUT_WALL": ("put_1", "Put wall", "put"),
    "PUT_WALL_2": ("put_2", "Put wall 2", "put"),
    "PUT_WALL_3": ("put_3", "Put wall 3", "put"),
}

_HEADER = re.compile(r"book=(\S+)\s+regime=(\S+)\s+mult=([\d.]+)")


def parse_levels(text: str) -> dict[str, Any]:
    """levels.txt → the seven levels, spot, and the header's regime. Pure."""
    out: dict[str, Any] = {
        "levels": [], "spot": None, "regime": None, "book": None,
        "generated_unix": None, "note": None,
    }
    if not text or text.lstrip().startswith("# unknown") or "# no snapshot" in text:
        out["note"] = text.strip().lstrip("# ") or "empty response"
        return out

    m = _HEADER.search(text)
    if m:
        out["book"], out["regime"] = m.group(1), m.group(2)

    raw: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "," not in line:
            continue
        k, _, v = line.partition(",")
        try:
            raw[k.strip().upper()] = float(v.strip())
        except ValueError:
            continue

    out["spot"] = raw.get("SPOT")
    out["generated_unix"] = raw.get("GENERATED_UNIX")

    spot = out["spot"]
    for key, (slug, label, side) in WANTED.items():
        price = raw.get(key)
        if price is None:
            continue
        out["levels"].append({
            "key": slug,
            "label": label,
            "side": side,
            "price": price,
            "dist": (price - spot) if spot else None,
            "dist_pct": ((price - spot) / spot * 100.0) if spot else None,
            # Rank within its side, so the UI can weight the first wall
            # heaviest without parsing the label.
            "rank": int(slug[-1]) if slug[-1].isdigit() else 1,
        })

    # Sorted high to low, which is how they sit on a chart. The panel draws
    # them as a ladder, so the order must be price order rather than the
    # file's key order (which groups by side).
    out["levels"].sort(key=lambda r: r["price"], reverse=True)
    return out


def collect(book: str = "front") -> tuple[dict[str, Any], SourceStatus]:
    """Levels for every configured asset. GEXYGEN absent is a normal state."""
    st = SourceStatus("GEXYGEN levels")
    if not GEXYGEN_API:
        st.error = "NT_GEXYGEN_API is empty — gamma panel disabled by configuration"
        st.notes.append("Set NT_GEXYGEN_API to the compute service to enable it.")
        return {"assets": {}, "enabled": False, "book": book}, st

    assets: dict[str, Any] = {}
    errors: list[str] = []
    for a in GEX_ASSETS:
        url = f"{GEXYGEN_API.rstrip('/')}/api/levels.txt?asset={a}&book={book}"
        # ttl 0: never serve a cached gamma level. A stale wall is worse than
        # no wall, and this upstream is on localhost — there is nothing to save.
        r = fetch(url, key=f"gex_{a}_{book}", ttl_sec=0.0, ua=UA, timeout=8, stale_ok=False)
        if not r.ok:
            errors.append(f"{a}: {r.error}")
            assets[a] = {"ok": False, "error": r.error, "levels": []}
            continue
        parsed = parse_levels(r.text)
        ok = bool(parsed["levels"])
        assets[a] = {
            "ok": ok,
            "error": None if ok else (parsed.get("note") or "no levels in response"),
            **parsed,
        }
        if not ok:
            errors.append(f"{a}: {assets[a]['error']}")

    live = sum(1 for v in assets.values() if v.get("ok"))
    st.ok = live > 0
    st.items = live
    st.source = "live" if st.ok else "unavailable"
    st.age_min = 0.0 if st.ok else None
    if errors:
        st.error = errors[0]
        if not st.ok:
            st.notes.append(f"Is GEXYGEN running? Expected at {GEXYGEN_API}")
    if st.ok:
        st.last_ok_utc = datetime.now(UTC).isoformat()

    return {"assets": assets, "enabled": True, "book": book}, st
