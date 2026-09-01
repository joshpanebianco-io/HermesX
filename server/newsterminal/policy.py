"""
What each FOMC meeting has priced into it, in basis points.

THE RATES PANEL DECLINED TO DO THIS ONCE, and the objection is worth quoting
because it was right at the time: a per-meeting number "needs a meeting
calendar, an assumed move size and a convention for a meeting that falls
mid-month — three assumptions stacked on a primitive that is already perfectly
readable." Two of the three have since dissolved. The meeting calendar is no
longer assumed — `fedcal` carries the Board's own schedule. And no move size is
assumed anywhere, because the output is BASIS POINTS PRICED, not "a 72% chance
of a cut": probability framing is what needs a quantum to divide by, and this
never divides. What remains is the day-count convention, one assumption, stated
below and tested.

THE ARITHMETIC. A fed funds future settles to the month's AVERAGE effective
rate, so `100 − price` blends the days before a meeting with the days after it.
With the decision date known, the blend un-mixes: if the old rate held for D
days of an N-day month,

    implied × N = pre × D + post × (N − D)   →   post = (implied·N − pre·D) / (N − D)

and `post − pre` is what that meeting has priced into it. The un-mixing chains:
each meeting's `post` is the next meeting's `pre`, anchored at the front by the
actual EFFR print.

THE ONE CONVENTION: a new target takes effect the day AFTER the decision, so a
decision on the 16th leaves the old rate on days 1–16 and the new rate on days
17–30. And when a meeting falls in the last days of its month, its own
contract barely sees the new rate — four post-meeting days out of thirty-one is
noise amplified eightfold — so the extraction switches to the first FOLLOWING
month with no meeting in it, whose whole average IS the post rate. Which method
produced each number travels with it as `method`.

PURE AND COMPUTED ON READ, like `volterm` and `expiry`: both inputs are already
on the board (the ZQ strip from `rates`, the schedule from `fedcal`), so this
is arithmetic, not a source, and there is no upstream for it to be stale
against.
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta
from typing import Any

# A decision this close to month-end leaves too few post-meeting days in its
# own contract for the un-mixing to be trusted; use the next clean month.
MIN_POST_DAYS = 5

# Below this, a meeting is "hold" — the strip carries a few tenths of noise.
HOLD_BAND_BP = 3.0

MAX_MEETINGS = 8


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _next_month(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


def meetings_priced(rates: dict[str, Any], fomc: list[dict[str, Any]]) -> dict[str, Any]:
    """The strip and the schedule → bp priced per meeting. Pure."""
    strip = {s["month"]: s.get("implied") for s in rates.get("strip") or [] if s.get("month")}
    effr = ((rates.get("policy") or {}).get("EFFR") or {}).get("rate")

    out: dict[str, Any] = {"meetings": [], "anchor": None, "anchor_src": None}
    if not strip or not fomc:
        return out

    # Decision days, ascending. `date` is a meeting's first day; a two-day
    # meeting decides on its last.
    decisions: list[date] = []
    for e in fomc:
        try:
            first = date.fromisoformat(str(e.get("date")))
        except (TypeError, ValueError):
            continue
        span = int(e.get("days") or 1)
        # Real date arithmetic: a meeting can span a month boundary (Jan 31 +
        # Feb 1 has happened), and clamping a day number would misdate it.
        decisions.append(first + timedelta(days=span - 1))
    decisions.sort()
    decision_months = {_month_key(d) for d in decisions}

    # The chain's anchor. EFFR is the actual traded rate and the honest start;
    # without it the front contract's implied stands in, and says so.
    if effr is not None:
        pre, src = float(effr), "EFFR"
    else:
        first_month = min(strip)
        pre, src = float(strip[first_month] or 0.0), "front contract"
    out["anchor"], out["anchor_src"] = round(pre, 3), src

    cum = 0.0
    for dd in decisions[:MAX_MEETINGS]:
        n_days = _cal.monthrange(dd.year, dd.month)[1]
        post_days = n_days - dd.day
        own = strip.get(_month_key(dd))

        post: float | None = None
        method: str | None = None

        if own is not None and post_days >= MIN_POST_DAYS:
            post = (own * n_days - pre * dd.day) / post_days
            method = "own month"
        else:
            # First following month with no meeting in it: its average IS the
            # post rate, no un-mixing needed.
            y, m = _next_month(dd.year, dd.month)
            for _ in range(3):
                key = f"{y:04d}-{m:02d}"
                if key in decision_months:
                    y, m = _next_month(y, m)
                    continue
                if strip.get(key) is not None:
                    post = float(strip[key])
                    method = "clean next month"
                break
            if post is None and own is not None and post_days > 0:
                post = (own * n_days - pre * dd.day) / post_days
                method = "own month (thin)"

        if post is None:
            break  # No contract reaches this meeting; nothing later can chain.

        move = (post - pre) * 100.0
        cum += move
        out["meetings"].append(
            {
                "date": dd.isoformat(),
                "label": dd.strftime("%b %d"),
                "move_bp": round(move, 1),
                "stance": (
                    "hike" if move > HOLD_BAND_BP
                    else "cut" if move < -HOLD_BAND_BP
                    else "hold"
                ),
                "implied_after": round(post, 3),
                "cum_bp": round(cum, 1),
                "method": method,
            }
        )
        pre = post

    return out
