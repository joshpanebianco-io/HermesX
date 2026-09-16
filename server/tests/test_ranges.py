"""
Session windows and what each row admits about itself.

THE BUG THESE ARE WRITTEN AGAINST. A London brief printed "The London session
opened at 29,263.75" — a real number lifted out of the digest's volume-profile
block, where it was the 18:00 ET Globex open, because the session rows carried
no open of their own and nothing said which day they were from. Two of these
tests are about the boundary; the rest are about a row being unable to pass
itself off as today's when it is not.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from newsterminal.sources.ranges import segment

ET = ZoneInfo("America/New_York")


def bars(start: datetime, count: int, first: float = 29200.0, step: float = 5.0) -> Any:
    """`count` 15-minute closes walking up from `first`, starting at `start`."""
    stamps, closes = [], []
    price = first
    for i in range(count):
        stamps.append(int((start + timedelta(minutes=15 * i)).timestamp()))
        closes.append(price)
        price += step
    return stamps, [None] * count, [None] * count, closes


def rows(now: datetime, start: datetime, count: int) -> dict[str, dict[str, Any]]:
    stamps, highs, lows, closes = bars(start, count)
    out = segment(stamps, highs, lows, closes, closes[-1], now)
    return {r["key"]: r for r in out if r["ok"]}


def test_london_is_the_open_window_0200_to_0500() -> None:
    """European futures open 08:00 CET — 02:00 ET — and the hour is theirs.

    It used to be counted as Asia, which described a European hour as thin
    Globex drift and disagreed with `resolve_session` by exactly one hour. It
    ENDS at 05:00 because "London took out the Asia high" is a claim about the
    open move, and a window running to 08:00 absorbs three hours of midday
    drift and stops meaning it.
    """
    r = rows(datetime(2026, 9, 16, 6, 0, tzinfo=ET), datetime(2026, 9, 15, 18, 0, tzinfo=ET), 52)
    assert r["asia"]["end_et"] == "01:45"      # last bar before the handover
    assert r["london"]["start_et"] == "02:00"
    assert r["london"]["end_et"] == "04:45"    # and it stops at 05:00
    assert r["euro_mid"]["start_et"] == "05:00"


def test_a_row_says_which_day_it_is_from() -> None:
    """Asia begins the evening BEFORE the session it feeds, so the dates differ."""
    r = rows(datetime(2026, 9, 16, 4, 0, tzinfo=ET), datetime(2026, 9, 15, 18, 0, tzinfo=ET), 40)
    assert r["asia"]["date"] == "Tue 15"
    assert r["london"]["date"] == "Wed 16"


def test_status_tracks_the_clock_not_the_bars() -> None:
    """The window containing `now` is live; every other one is complete.

    Without this the range still being built reads exactly like a finished one,
    which is the same trap the volume profile's developing row was given labels
    to avoid.
    """
    start = datetime(2026, 9, 15, 18, 0, tzinfo=ET)
    during_asia = rows(datetime(2026, 9, 16, 1, 0, tzinfo=ET), start, 40)
    assert during_asia["asia"]["status"] == "live"

    during_london = rows(datetime(2026, 9, 16, 4, 0, tzinfo=ET), start, 40)
    assert during_london["asia"]["status"] == "complete"
    assert during_london["london"]["status"] == "live"


def test_every_row_carries_an_open() -> None:
    """The field whose absence sent a model looking elsewhere for one."""
    r = rows(datetime(2026, 9, 16, 4, 0, tzinfo=ET), datetime(2026, 9, 15, 18, 0, tzinfo=ET), 40)
    assert r["asia"]["open"] == 29200.0          # the 18:00 print
    assert r["london"]["open"] == 29360.0        # the 02:00 print, a different number
    assert r["asia"]["open"] != r["london"]["open"]


def test_windows_do_not_overlap_or_leave_a_gap() -> None:
    """Every hour of the clock belongs to exactly one window."""
    from newsterminal.sources.ranges import WINDOWS, _in_window

    for tenth in range(240):
        hour = tenth / 10.0
        owners = [k for k, _, s, e in WINDOWS if _in_window(hour, s, e)]
        # 16:00-18:00 is the post-close lull and belongs to nothing.
        assert len(owners) <= 1, (hour, owners)
        if not (16.0 <= hour < 18.0):
            assert len(owners) == 1, (hour, owners)
