"""
The volume profile's two invertible rules, pinned.

The value-area expansion can silently take the wrong neighbour and still
produce plausible numbers, and the window clock decides which anchor a
session reads — 18:00 for Asia/London, 09:30 for New York — which is the
owner's spec in one function. Get either wrong and the levels look fine and
mean something else.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from newsterminal.profile import ET, assemble, build, pick_bin, windows

NY = ZoneInfo("America/New_York")


def at(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=ET)


# --- build() ------------------------------------------------------------------


def test_poc_is_where_the_volume_concentrates() -> None:
    # DENSITY WINS, NOT HEADLINE VOLUME — the property that makes it a
    # profile. Ten bars of 100 stacked on one point put ~250 per bin there;
    # a single 300-volume bar spread over its own point puts only ~75 per
    # bin at 110. The cluster is the POC.
    bars = [(100.5, 99.5, 100.0)] * 10 + [(110.5, 109.5, 300.0)]
    p = build(bars)
    assert p is not None
    assert abs(p["poc"] - 100.0) < 1.0
    # Make the far bar genuinely denser and the POC must move to it.
    bars = [(100.5, 99.5, 100.0)] * 10 + [(110.5, 109.5, 2000.0)]
    p2 = build(bars)
    assert p2 is not None
    assert abs(p2["poc"] - 110.0) < 1.0


def test_value_area_holds_seventy_percent_around_the_poc() -> None:
    # A clean pyramid: volume 1..5..1 across nine adjacent one-point bars.
    weights = [1, 2, 3, 4, 5, 4, 3, 2, 1]
    bars = [(100.0 + i + 0.5, 100.0 + i, float(w) * 10) for i, w in enumerate(weights)]
    p = build(bars)
    assert p is not None
    assert abs(p["poc"] - 104.5) < 1.0  # the apex
    # 70% of 250 = 175; the middle five bins hold 190, the middle three 130 —
    # so the area must span roughly the middle five: VAL near 102, VAH near 107.
    assert p["val"] <= 103.2  # one 0.1 bin of grid slack
    assert p["vah"] >= 106.0
    # And it must NOT swallow the wings.
    assert p["val"] >= 100.5
    assert p["vah"] <= 108.6


def test_a_bars_volume_is_split_by_overlap() -> None:
    # One bar spanning exactly two one-point bins, half in each.
    bars = [(101.0, 99.0, 100.0)] * 6  # MIN_BARS
    p = build(bars)
    assert p is not None
    assert p["low"] == 99.0 and p["high"] == 101.0


def test_no_volume_no_profile() -> None:
    assert build([(100.5, 99.5, 0.0)] * 10) is None
    assert build([]) is None
    assert build([(100.5, 99.5, 5.0)] * 3) is None  # under MIN_BARS


def test_bin_ladder_targets_sixty() -> None:
    assert pick_bin(29300, 29550) == 5.0  # 250 pts -> 50 bins
    assert pick_bin(4470, 4500) == 0.5  # 30 pts -> 60 bins


# --- windows(): the owner's session spec -------------------------------------


def test_new_york_reads_all_three_with_a_0930_anchor() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 1, 11, 0))}  # Tue 11:00 ET
    assert set(ws) == {"prev_rth", "overnight", "dev"}
    assert ws["prev_rth"]["start"] == at(2026, 8, 31, 9, 30)  # Monday's cash
    assert ws["overnight"]["start"] == at(2026, 8, 31, 18, 0)
    assert ws["overnight"]["end"] == at(2026, 9, 1, 9, 30)
    assert ws["dev"]["start"] == at(2026, 9, 1, 9, 30)
    assert ws["dev"]["label"].endswith("09:30")


def test_asia_evening_reads_prev_rth_plus_an_1800_anchor() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 8, 31, 21, 30))}  # Mon 21:30 ET
    assert set(ws) == {"prev_rth", "dev"}  # the overnight IS the developing
    assert ws["prev_rth"]["start"] == at(2026, 8, 31, 9, 30)  # today's cash
    assert ws["dev"]["start"] == at(2026, 8, 31, 18, 0)
    assert ws["dev"]["label"].endswith("18:00")


def test_london_morning_keeps_yesterdays_1800_anchor() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 1, 4, 0))}  # Tue 04:00 ET
    assert set(ws) == {"prev_rth", "dev"}
    assert ws["prev_rth"]["start"] == at(2026, 8, 31, 9, 30)
    assert ws["dev"]["start"] == at(2026, 8, 31, 18, 0)  # yesterday evening


def test_post_close_lull_has_nothing_developing() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 1, 16, 30))}
    assert set(ws) == {"prev_rth", "overnight"}
    assert ws["prev_rth"]["start"] == at(2026, 9, 1, 9, 30)  # today's, complete


def test_sunday_evening_reads_fridays_cash() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 6, 19, 0))}  # Sun 19:00 ET
    assert ws["prev_rth"]["start"] == at(2026, 9, 4, 9, 30)  # Friday
    assert ws["dev"]["start"] == at(2026, 9, 6, 18, 0)


def test_monday_0100_anchors_sunday_1800() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 7, 1, 0))}  # Mon 01:00 ET
    assert ws["prev_rth"]["start"] == at(2026, 9, 4, 9, 30)  # Friday
    assert ws["dev"]["start"] == at(2026, 9, 6, 18, 0)  # Sunday evening


def test_saturday_develops_nothing() -> None:
    ws = {w["key"]: w for w in windows(at(2026, 9, 5, 12, 0))}  # Saturday
    assert "dev" not in ws


# --- assemble(): the holiday walk-back ---------------------------------------


def test_a_holiday_slides_prev_rth_back_a_day() -> None:
    """Monday is a holiday (no bars); Tuesday 21:00 must read Friday's cash."""
    fri = at(2026, 9, 4, 9, 30)
    stamps, highs, lows, vols = [], [], [], []
    # Friday RTH bars only.
    t = fri
    for i in range(78):
        stamps.append(int(t.timestamp()))
        highs.append(101.0 + (i % 3))
        lows.append(99.0 + (i % 3))
        vols.append(50.0)
        t = datetime.fromtimestamp(t.timestamp() + 300, ET)
    # Tuesday evening, after a barless Monday.
    rows = assemble(stamps, highs, lows, vols, at(2026, 9, 8, 21, 0))
    keys = {r["key"]: r for r in rows}
    assert "prev_rth" in keys
    assert keys["prev_rth"]["date"] == "Fri 04"
    # No Tuesday-evening bars exist, so nothing develops.
    assert "dev" not in keys


@pytest.mark.parametrize("kind_key", ["prev_rth", "dev"])
def test_assemble_labels_carry_kind(kind_key: str) -> None:
    now = at(2026, 8, 31, 21, 0)
    start = at(2026, 8, 31, 9, 30) if kind_key == "prev_rth" else at(2026, 8, 31, 18, 0)
    stamps, highs, lows, vols = [], [], [], []
    t = start
    for _ in range(20):
        stamps.append(int(t.timestamp()))
        highs.append(100.5)
        lows.append(99.5)
        vols.append(10.0)
        t = datetime.fromtimestamp(t.timestamp() + 300, ET)
    rows = {r["key"]: r for r in assemble(stamps, highs, lows, vols, now)}
    assert kind_key in rows
    assert rows[kind_key]["kind"] == ("live" if kind_key == "dev" else "done")
