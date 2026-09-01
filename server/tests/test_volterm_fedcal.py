"""
The two rules here are invertible — wrong in a way that still looks right.

`volterm` decides which end of the curve means trouble. Flip the ratio and it
reports calm during a panic, with no error and no missing data. `fedcal` turns
"3,4" into a date; read the wrong end and a two-day FOMC lands on its second
day, a day late for anyone positioning into it.
"""

from __future__ import annotations

from datetime import date

import pytest

from newsterminal import volterm
from newsterminal.sources import fedcal


def q(key: str, last: float, pct: float | None = None) -> dict:
    return {"key": key, "last": last, "pct": pct}


# --- volterm -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("vix", "vix3m", "shape"),
    [
        # The calm shape: the quarter prices more vol than the month.
        (15.0, 18.0, "contango"),
        # The stressed shape: the month overtakes the quarter.
        (28.0, 22.0, "backwardation"),
        # Inside FLAT_BAND either side of 1.00 — not saying anything yet.
        (20.0, 20.0, "flat"),
        (20.1, 20.0, "flat"),
        (19.9, 20.0, "flat"),
    ],
)
def test_shape_follows_the_ratio(vix: float, vix3m: float, shape: str) -> None:
    st = volterm.state([q("VIX", vix), q("VIX3M", vix3m)])
    assert st["shape"] == shape
    assert st["ratio"] == pytest.approx(vix / vix3m, abs=1e-4)


def test_band_edges_are_the_boundary() -> None:
    """Just outside FLAT_BAND is a verdict; just inside is not."""
    over = volterm.state([q("VIX", 100 * (1 + volterm.FLAT_BAND) + 0.5), q("VIX3M", 100.0)])
    under = volterm.state([q("VIX", 100 * (1 - volterm.FLAT_BAND) - 0.5), q("VIX3M", 100.0)])
    assert over["shape"] == "backwardation"
    assert under["shape"] == "contango"


def test_missing_tenors_degrade_rather_than_raise() -> None:
    st = volterm.state([q("VIX9D", 12.0)])
    assert st["shape"] == "unknown"
    assert st["ratio"] is None
    assert [p["key"] for p in st["points"]] == ["VIX9D"]


def test_points_keep_curve_order_not_quote_order() -> None:
    """The panel draws them top to bottom; the quote list is unordered."""
    st = volterm.state([q("VIX6M", 20.0), q("VIX", 15.0), q("VIX3M", 18.0), q("VIX9D", 12.0)])
    assert [p["key"] for p in st["points"]] == ["VIX9D", "VIX", "VIX3M", "VIX6M"]


def test_a_null_last_is_not_a_zero() -> None:
    st = volterm.state([q("VIX", 15.0), q("VIX3M", 18.0), {"key": "VIX9D", "last": None}])
    assert [p["key"] for p in st["points"]] == ["VIX", "VIX3M"]
    assert st["shape"] == "contango"


# --- fedcal ------------------------------------------------------------------

TODAY = date(2026, 9, 1)


def ev(**kw) -> dict:
    base = {
        "type": "Speeches",
        "month": "2026-09",
        "days": "3",
        "time": "8:30 a.m.",
        "title": "Speech - Governor X",
    }
    return {**base, **kw}


def test_two_day_meeting_schedules_against_the_first_day() -> None:
    meeting = ev(type="FOMC", days="16,17", title="FOMC Meeting", time="2:00 p.m.")
    (row,) = fedcal.parse([meeting], TODAY)
    assert row["date"] == "2026-09-16"
    assert row["days"] == 2
    assert row["in_days"] == 15


def test_stat_releases_are_dropped() -> None:
    assert fedcal.parse([ev(type="Stat", title="H.15 Selected Interest Rates")], TODAY) == []


def test_the_past_and_the_far_future_are_both_out_of_the_window() -> None:
    rows = fedcal.parse(
        [ev(days="1", month="2026-08"), ev(days="3"), ev(days="15", month="2026-10")],
        TODAY,
    )
    assert [r["date"] for r in rows] == ["2026-09-03"]


@pytest.mark.parametrize(
    ("raw", "et"),
    [
        ("8:30 a.m.", "08:30"),
        ("2:00 p.m.", "14:00"),
        ("12:00 p.m.", "12:00"),  # noon is 12, not 24
        ("12:30 a.m.", "00:30"),  # midnight is 0, not 12
        ("", None),
        ("TBA", None),
    ],
)
def test_et_times_parse_across_the_noon_boundary(raw: str, et: str | None) -> None:
    (row,) = fedcal.parse([ev(time=raw)], TODAY)
    assert row["et"] == et
    assert (row["utc"] is None) == (et is None)


def test_principals_are_major_and_a_panellist_is_not() -> None:
    rows = fedcal.parse(
        [
            ev(days="3", title="Speech - Governor Christopher J. Waller"),
            ev(days="4", type="Conferences", title="Community Banking Research Conference"),
            ev(days="5", type="Beige", title="Beige Book"),
        ],
        TODAY,
    )
    assert [r["major"] for r in rows] == [True, False, True]


def test_escaped_html_is_stripped_from_titles() -> None:
    (row,) = fedcal.parse([ev(title="Speech &amp; <em>Discussion</em> - Chair Powell")], TODAY)
    assert row["title"] == "Speech & Discussion - Chair Powell"
    assert row["major"] is True


def test_rows_sort_by_date_then_time_with_untimed_last() -> None:
    rows = fedcal.parse(
        [ev(days="3", time="2:00 p.m."), ev(days="3", time=""), ev(days="2", time="9:00 a.m.")],
        TODAY,
    )
    assert [(r["date"], r["et"]) for r in rows] == [
        ("2026-09-02", "09:00"),
        ("2026-09-03", "14:00"),
        ("2026-09-03", None),
    ]


def test_a_malformed_day_is_skipped_not_fatal() -> None:
    rows = fedcal.parse([ev(days="31", month="2026-09"), ev(days="3")], TODAY)
    assert [r["date"] for r in rows] == ["2026-09-03"]
