"""
The session clock's headline must never contradict the list printed under it.

That is the invariant these tests exist for. `_phase` returns one line — "Asia
session", "Globex", "Weekend" — and the panel prints it directly above the seven
city rows. When the two are derived independently they drift, and the drift is
invisible to every type checker and every unit test that only looks at one side.

The bug this locks down, reported 2026-08-31 at 20:51 ET: the label read
"Globex — New futures session under way" while Sydney and Tokyo were both marked
OPEN two lines below it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from newsterminal.sessions import _ASIA, _EUROPE, session_state

ET = ZoneInfo("America/New_York")


def at(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def phase(when: datetime) -> str:
    return session_state(when)["phase"]["key"]


def live(when: datetime) -> set[str]:
    return {r["key"] for r in session_state(when)["sessions"] if r["open"]}


# --- the invariant ------------------------------------------------------------


def test_the_headline_never_contradicts_the_rows() -> None:
    """Ten days at 15-minute resolution, across a weekend."""
    bad: list[str] = []
    when = at(2026, 8, 28, 0, 0)  # a Friday
    for _ in range(4 * 24 * 10):
        st = session_state(when)
        key = st["phase"]["key"]
        open_now = {r["key"] for r in st["sessions"] if r["open"]}
        asia, euro = bool(open_now & _ASIA), bool(open_now & _EUROPE)
        stamp = when.strftime("%a %d %H:%M")
        if key == "globex" and (asia or euro):
            bad.append(f"{stamp}: says Globex, {sorted(open_now)} open")
        if key == "asia" and not asia:
            bad.append(f"{stamp}: says Asia, no Asian desk open")
        if key == "london" and not euro:
            bad.append(f"{stamp}: says London, no European desk open")
        if key == "weekend" and open_now:
            bad.append(f"{stamp}: says Weekend, {sorted(open_now)} open")
        when += timedelta(minutes=15)
    assert bad == []


# --- the reported bug ---------------------------------------------------------


def test_the_asian_evening_is_not_globex() -> None:
    when = at(2026, 8, 31, 20, 51)
    assert live(when) == {"sydney", "tokyo"}
    assert phase(when) == "asia"


def test_globex_is_only_the_hours_with_nothing_cash_open() -> None:
    """18:00-20:00 ET in August is genuinely futures-only, and says so."""
    assert live(at(2026, 8, 31, 18, 30)) == set()
    assert phase(at(2026, 8, 31, 18, 30)) == "globex"


def test_the_same_et_clock_changes_meaning_across_the_dst_swing() -> None:
    """
    THE REASON THE PHASE IS DERIVED RATHER THAN BUCKETED.

    Sydney keeps southern-hemisphere DST and New York keeps northern, so
    Sydney's open swings between 18:00 and 20:00 ET over the year. 18:30 ET is
    futures-only in August and mid-Asia in January; no ET constant is right for
    both, which is why a corrected bucket would not have been a fix.
    """
    assert phase(at(2026, 8, 31, 18, 30)) == "globex"
    assert phase(at(2027, 1, 12, 18, 30)) == "asia"


# --- the week's real boundaries ----------------------------------------------


@pytest.mark.parametrize(
    ("when", "key"),
    [
        # Friday: cash shuts 16:00, futures settle and stop at 17:00.
        (at(2026, 8, 28, 16, 30), "post"),
        (at(2026, 8, 28, 17, 30), "weekend"),
        (at(2026, 8, 29, 12, 0), "weekend"),  # Saturday
        (at(2026, 8, 30, 12, 0), "weekend"),  # Sunday, before the reopen
        # Sunday 18:00 ET IS the new week — and 08:00 Monday in Sydney, which is
        # this desk's own Monday morning.
        (at(2026, 8, 30, 18, 30), "globex"),
        (at(2026, 8, 30, 21, 0), "asia"),
    ],
)
def test_the_week_is_bounded_by_globex_not_the_calendar(when: datetime, key: str) -> None:
    assert phase(when) == key


@pytest.mark.parametrize(
    ("hour", "minute", "key"),
    [
        (3, 30, "handover"),  # Hong Kong still trading as Europe arrives
        (5, 0, "london"),
        (8, 30, "preopen"),
        (10, 0, "open"),
        (12, 30, "midday"),
        (15, 0, "close"),
        (16, 30, "post"),
    ],
)
def test_the_new_york_ladder_keeps_its_own_clock(hour: int, minute: int, key: str) -> None:
    """ET is New York's local time, so these boundaries are exact year-round."""
    assert phase(at(2026, 9, 1, hour, minute)) == key
