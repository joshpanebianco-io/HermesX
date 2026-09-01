"""
The volatility term structure — what the options market thinks happens next.

WHY IT EARNS A PANEL WHEN THE BOARD ALREADY CARRIES VIX. A single VIX level
says how much movement is priced for the next thirty days and nothing about
whether that is unusual. The CURVE says whether the market is calm or
frightened, because the shape inverts before the level moves much: in normal
conditions each further tenor prices more vol than the one before it
(contango), and when something is actually wrong the near tenor overtakes the
far one (backwardation). That crossover is one of the cleanest regime signals
available and it typically leads the equity move rather than following it.

IT PAIRS WITH THE GAMMA REGIME AND ANSWERS A DIFFERENT QUESTION. Gamma says how
dealers must hedge — dampening moves or amplifying them. Term structure says
what the options market expects over the next month. Positive gamma with a
curve tipping into backwardation is a different session from positive gamma
with a curve in healthy contango, and nothing else on the terminal separates
those two.

COMPUTED ON READ, NOT POLLED. Every input is already on the board, so this is
arithmetic rather than a source — the same standing as `expiry`. There is no
upstream here to be stale against.
"""

from __future__ import annotations

from typing import Any

# key, label, roughly how far out it prices
TENORS: list[tuple[str, str, str]] = [
    ("VIX9D", "9-day", "this week"),
    ("VIX", "30-day", "the next month"),
    ("VIX3M", "3-month", "the quarter"),
    ("VIX6M", "6-month", "half a year"),
]

# The near/far pair everyone actually quotes. Above 1.00 the near tenor prices
# more vol than the far one, which is backwardation.
HEADLINE_PAIR = ("VIX", "VIX3M")

# A curve is never exactly flat, and calling a 0.4% steepness "backwardation"
# would fire this signal most weeks. 1.00 is the real boundary; the band around
# it is where the shape is not saying anything yet.
FLAT_BAND = 0.02


def _q(quotes: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next((q for q in quotes if q.get("key") == key), None)


def state(quotes: list[dict[str, Any]]) -> dict[str, Any]:
    """The curve, its shape, and what the shape means."""
    points: list[dict[str, Any]] = []
    for key, label, horizon in TENORS:
        q = _q(quotes, key)
        if q is None or q.get("last") is None:
            continue
        points.append(
            {
                "key": key,
                "label": label,
                "horizon": horizon,
                "value": q["last"],
                "pct": round(q["pct"], 2) if q.get("pct") is not None else None,
            }
        )

    near = _q(quotes, HEADLINE_PAIR[0])
    far = _q(quotes, HEADLINE_PAIR[1])
    ratio = None
    if near and far and far.get("last"):
        ratio = near["last"] / far["last"]

    if ratio is None:
        shape, note = "unknown", None
    elif ratio > 1 + FLAT_BAND:
        shape = "backwardation"
        note = (
            "Near-dated vol is bid above the quarter — the market is paying up for "
            "protection now rather than later. This is the stressed shape, and it "
            "usually turns before the index does."
        )
    elif ratio < 1 - FLAT_BAND:
        shape = "contango"
        note = (
            "Each tenor prices more vol than the one before it — the normal, calm "
            "shape. A move toward 1.00 is the thing to watch, not the level."
        )
    else:
        shape = "flat"
        note = (
            "The curve is flat within a couple of percent. Neither calm nor "
            "stressed; the next move in the ratio decides which."
        )

    # Not a tenor of the curve, so it sits beside it rather than in it: SKEW
    # prices the cost of far out-of-the-money puts against at-the-money, which
    # is what the market is paying for a crash rather than for movement.
    skew = _q(quotes, "SKEW")

    return {
        "points": points,
        "ratio": round(ratio, 4) if ratio is not None else None,
        "ratio_label": f"{HEADLINE_PAIR[0]}/{HEADLINE_PAIR[1]}",
        "shape": shape,
        "note": note,
        "skew": skew["last"] if skew else None,
        "skew_pct": round(skew["pct"], 2) if skew and skew.get("pct") is not None else None,
    }
