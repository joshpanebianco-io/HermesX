"""
Volume profile — where the volume actually traded, cut the way the desk trades.

THREE WINDOWS, AND WHICH ONES EXIST DEPENDS ON THE CLOCK (owner spec,
2026-09-01):

  prev RTH     the most recent COMPLETED 09:30-16:00 ET cash session — the
               reference levels everyone marks before any session.
  overnight    the completed 18:00 -> 09:30 Globex session. Only distinct
               from "developing" during and after the NY day it preceded;
               while Asia or London is trading, the overnight IS the
               developing profile and showing it twice would be the same
               numbers under two names.
  developing   anchored 18:00 ET while Asia/London trade, re-anchored 09:30
               once New York opens. The live one.

THE LEVELS, not the histogram. POC is the price with the most volume (the
magnet), VAH/VAL bound the 70% value area (acceptance). They are read beside
the gamma walls: a put wall sitting on yesterday's VAL is confluence, and
confluence is the whole reason these numbers are on a news terminal.

APPROXIMATE BY CONSTRUCTION, AND LABELLED AS SUCH. True profiles are built
from ticks; these are built from 5-minute bars with each bar's volume spread
uniformly across its high-low range. On most days POC lands within a couple
of ticks of the exchange-accurate figure; on fast trend days it can sit a
node away. Context-grade, not execution-grade — the chart platforms own the
execution-grade version.

PURE. Bars in, levels out; the fetch lives in sources/profiles.py.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
GLOBEX_OPEN = time(18, 0)

# The value area convention: the smallest set of bins around the POC holding
# this share of the window's volume. 70% is the standard nobody argues with.
VALUE_AREA = 0.70

# Bin sizes are chosen from a ladder of prices a human would quote, targeting
# roughly this many bins across the window — enough resolution to separate
# nodes, few enough that 5m bars can fill them meaningfully.
TARGET_BINS = 60
NICE_STEPS = [0.1, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 25.0, 50.0]

# A window with fewer traded bars than this has no profile worth stating.
MIN_BARS = 6


def pick_bin(lo: float, hi: float) -> float:
    """The nice step that lands nearest TARGET_BINS across [lo, hi]."""
    span = max(hi - lo, 1e-9)
    return min(NICE_STEPS, key=lambda s: abs(span / s - TARGET_BINS))


def build(
    bars: list[tuple[float, float, float]],
) -> dict[str, Any] | None:
    """(high, low, volume) bars -> {poc, vah, val, low, high, volume, bin}.

    Each bar's volume is spread uniformly across the bins its range overlaps,
    proportional to the overlap — a bar that clips the top of a bin gives that
    bin only the clipped share. The value area grows outward from the POC,
    taking whichever neighbouring bin is heavier, until it holds VALUE_AREA of
    the total. That is the classic expansion; ties go higher, which matches
    the convention charting platforms use.
    """
    bars = [(h, low, v) for h, low, v in bars if v and v > 0 and h is not None and low is not None]
    if len(bars) < MIN_BARS:
        return None

    lo = min(b[1] for b in bars)
    hi = max(b[0] for b in bars)
    if hi <= lo:
        return None
    step = pick_bin(lo, hi)
    base = int(lo / step) * step  # snap the first edge to the grid
    nbins = int((hi - base) / step) + 1
    vol = [0.0] * nbins

    for h, low_, v in bars:
        top = max(h, low_)
        bot = min(h, low_)
        if top == bot:
            i = min(nbins - 1, max(0, int((bot - base) / step)))
            vol[i] += v
            continue
        span = top - bot
        i0 = max(0, int((bot - base) / step))
        i1 = min(nbins - 1, int((top - base) / step))
        for i in range(i0, i1 + 1):
            b_lo = base + i * step
            b_hi = b_lo + step
            overlap = min(top, b_hi) - max(bot, b_lo)
            if overlap > 0:
                vol[i] += v * (overlap / span)

    total = sum(vol)
    if total <= 0:
        return None

    poc_i = max(range(nbins), key=lambda i: (vol[i], i))  # ties go higher
    in_area = {poc_i}
    acc = vol[poc_i]
    lo_i = hi_i = poc_i
    while acc < VALUE_AREA * total and (lo_i > 0 or hi_i < nbins - 1):
        up = vol[hi_i + 1] if hi_i < nbins - 1 else -1.0
        dn = vol[lo_i - 1] if lo_i > 0 else -1.0
        if up >= dn:
            hi_i += 1
            acc += max(up, 0.0)
            in_area.add(hi_i)
        else:
            lo_i -= 1
            acc += max(dn, 0.0)
            in_area.add(lo_i)

    centre = lambda i: base + i * step + step / 2  # noqa: E731

    # THE SHAPE, in market-profile vocabulary, from where the volume sits.
    # POC in the upper third is a P (acceptance near the highs, the
    # short-covering look); lower third is a b (acceptance low, the long-
    # liquidation look); the middle is balance. A second node at least 40%
    # of the POC's weight, separated by a valley under half the lesser
    # peak, marks a double distribution — two auctions in one window, and
    # the valley between them is the reference the day trades around.
    poc_pos = (centre(poc_i) - lo) / max(hi - lo, 1e-9)
    shape = "P (accepted high)" if poc_pos >= 0.66 else (
        "b (accepted low)" if poc_pos <= 0.34 else "D (balanced)"
    )
    second_i = None
    for i in range(nbins):
        if i == poc_i or vol[i] < 0.4 * vol[poc_i]:
            continue
        a, b = sorted((i, poc_i))
        valley = min(vol[a:b + 1]) if b > a else vol[a]
        deep_valley = valley < 0.5 * min(vol[i], vol[poc_i])
        if deep_valley and (second_i is None or vol[i] > vol[second_i]):
            second_i = i
    if second_i is not None:
        shape = "double distribution"

    return {
        "poc": round(centre(poc_i), 4),
        "poc_pos": round(poc_pos, 2),
        "shape": shape,
        "second_node": round(centre(second_i), 4) if second_i is not None else None,
        "vah": round(base + (hi_i + 1) * step, 4),
        "val": round(base + lo_i * step, 4),
        "low": round(lo, 4),
        "high": round(hi, 4),
        "volume": round(total),
        "bin": step,
        "bars": len(bars),
    }


def value_position(price: float | None, vah: float | None, val: float | None) -> str | None:
    """Above value, inside value, or below value — the market-profile read.

    One classifier used for BOTH facts the report states: where the session
    OPENED relative to prior value, and where price trades NOW relative to
    each reference window. Inside is val <= p <= vah inclusive, so a print
    sitting exactly on the edge is "inside" — an auction touching its
    boundary has not left it.
    """
    if price is None or vah is None or val is None:
        return None
    if price > vah:
        return "above_value"
    if price < val:
        return "below_value"
    return "inside_value"


def prev_trading_day(d: datetime) -> datetime:
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def windows(now_et: datetime) -> list[dict[str, Any]]:
    """Which profiles exist right now, and their [start, end) instants.

    The developing window's anchor is the spec's whole point: 18:00 ET while
    Asia and London trade, 09:30 once New York opens. The overnight appears
    as its own row only once it is COMPLETE — while it is still forming it
    is the developing profile, and one set of numbers should not wear two
    names.
    """
    d = now_et.date()
    t = now_et.time()

    def at(day: Any, tm: time) -> datetime:
        return datetime(day.year, day.month, day.day, tm.hour, tm.minute, tzinfo=ET)

    out: list[dict[str, Any]] = []

    if RTH_OPEN <= t < RTH_CLOSE and now_et.weekday() < 5:
        # New York is trading: yesterday's cash, the completed overnight, and
        # the live RTH profile off the 09:30 anchor.
        prev = prev_trading_day(now_et)
        out.append({"key": "prev_rth", "label": "Prev RTH", "kind": "done",
                    "start": at(prev, RTH_OPEN), "end": at(prev, RTH_CLOSE)})
        out.append({"key": "overnight", "label": "Overnight", "kind": "done",
                    "start": at(prev, GLOBEX_OPEN), "end": at(d, RTH_OPEN)})
        out.append({"key": "dev", "label": "Live · 09:30", "kind": "live",
                    "start": at(d, RTH_OPEN), "end": now_et})
    elif RTH_CLOSE <= t < GLOBEX_OPEN and now_et.weekday() < 5:
        # Post-close lull: today's cash just completed; nothing develops
        # until Globex reopens at 18:00.
        prev = prev_trading_day(now_et)
        out.append({"key": "prev_rth", "label": "RTH (today)", "kind": "done",
                    "start": at(d, RTH_OPEN), "end": at(d, RTH_CLOSE)})
        out.append({"key": "overnight", "label": "Overnight", "kind": "done",
                    "start": at(prev, GLOBEX_OPEN), "end": at(d, RTH_OPEN)})
    elif t >= GLOBEX_OPEN:
        # Globex evening (Asia). Sunday's reference cash day is Friday.
        rth_day = d if now_et.weekday() < 5 else prev_trading_day(now_et).date()
        out.append({"key": "prev_rth", "label": "Prev RTH", "kind": "done",
                    "start": at(rth_day, RTH_OPEN), "end": at(rth_day, RTH_CLOSE)})
        out.append({"key": "dev", "label": "Live · 18:00", "kind": "live",
                    "start": at(d, GLOBEX_OPEN), "end": now_et})
    else:
        # Globex morning (late Asia / London / pre-NY), t < 09:30. The anchor
        # is yesterday 18:00 by the calendar — which on Monday morning is
        # Sunday, where the bars genuinely start.
        anchor_day = d - timedelta(days=1)
        prev = prev_trading_day(now_et)
        out.append({"key": "prev_rth", "label": "Prev RTH", "kind": "done",
                    "start": at(prev, RTH_OPEN), "end": at(prev, RTH_CLOSE)})
        if now_et.weekday() < 5 and anchor_day.weekday() != 5:  # Saturday has no bars
            out.append({"key": "dev", "label": "Live · 18:00", "kind": "live",
                        "start": at(anchor_day, GLOBEX_OPEN), "end": now_et})

    return out


def assemble(
    stamps: list[int],
    highs: list[float | None],
    lows: list[float | None],
    vols: list[float | None],
    now_et: datetime,
    opens: list[float | None] | None = None,
) -> list[dict[str, Any]]:
    """Bars + the clock -> the profile rows the panel and digest show.

    The prev-RTH window walks back up to four trading days if its first
    candidate has no bars — that is what quietly absorbs exchange holidays
    without a holiday calendar.
    """
    rows: list[dict[str, Any]] = []
    for w in windows(now_et):
        start, end = w["start"], w["end"]
        tries = 0
        while True:
            s_ts, e_ts = start.timestamp(), end.timestamp()
            idxs = [i for i in range(len(stamps)) if s_ts <= stamps[i] < e_ts]
            picked = [(highs[i], lows[i], vols[i] or 0.0) for i in idxs]
            # The window's OPENING PRINT — the fact "opened above/inside/
            # below prior value" is judged from. First bar with an open.
            w_open = None
            if opens is not None:
                for i in idxs:
                    if opens[i] is not None:
                        w_open = opens[i]
                        break
            prof = build([(h, low, v) for h, low, v in picked if h is not None and low is not None])
            if prof is not None or w["key"] != "prev_rth" or tries >= 4:
                break
            # A holiday: slide the whole RTH window back one trading day.
            prev = prev_trading_day(start)
            start = datetime(
                prev.year, prev.month, prev.day, RTH_OPEN.hour, RTH_OPEN.minute, tzinfo=ET
            )
            end = datetime(
                prev.year, prev.month, prev.day, RTH_CLOSE.hour, RTH_CLOSE.minute, tzinfo=ET
            )
            tries += 1
        if prof is None:
            continue
        rows.append({
            **prof,
            "open": round(w_open, 4) if w_open is not None else None,
            "key": w["key"],
            "label": w["label"],
            "kind": w["kind"],
            "date": start.strftime("%a %d"),
            "start_et": start.strftime("%H:%M"),
            "end_et": "now" if w["kind"] == "live" else end.strftime("%H:%M"),
        })
    return rows
