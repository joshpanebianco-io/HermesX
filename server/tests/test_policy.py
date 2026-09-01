"""
The per-meeting un-mixing, pinned down.

Every rule here is invertible — wrong in a way that still produces plausible
numbers. Flip the day-count and a hike shrinks instead of growing; anchor the
chain on the wrong rate and every meeting inherits the error; read a
late-month meeting from its own contract and four days of noise print as
twenty basis points of conviction.
"""

from __future__ import annotations

import pytest

from newsterminal.policy import meetings_priced


def rates(effr: float | None, strip: dict[str, float]) -> dict:
    return {
        "policy": {"EFFR": {"rate": effr}} if effr is not None else {},
        "strip": [{"month": k, "implied": v} for k, v in strip.items()],
    }


def meeting(date: str, days: int = 2) -> dict:
    return {"date": date, "days": days}


def test_a_flat_strip_prices_nothing() -> None:
    pm = meetings_priced(
        rates(3.63, {"2026-09": 3.63, "2026-10": 3.63, "2026-11": 3.63}),
        [meeting("2026-09-15")],
    )
    (m,) = pm["meetings"]
    assert m["stance"] == "hold"
    assert abs(m["move_bp"]) < 0.001


def test_the_unmixing_recovers_a_known_hike_exactly() -> None:
    """Built backwards from the answer: 3.63 for 16 days, 3.88 for 14."""
    implied_sep = (3.63 * 16 + 3.88 * 14) / 30
    pm = meetings_priced(rates(3.63, {"2026-09": implied_sep}), [meeting("2026-09-15")])
    (m,) = pm["meetings"]
    assert m["move_bp"] == pytest.approx(25.0, abs=0.1)
    assert m["implied_after"] == pytest.approx(3.88, abs=0.001)
    assert m["stance"] == "hike"
    assert m["method"] == "own month"


def test_a_cut_carries_its_sign() -> None:
    implied = (4.33 * 16 + 4.08 * 14) / 30
    pm = meetings_priced(rates(4.33, {"2026-09": implied}), [meeting("2026-09-15")])
    (m,) = pm["meetings"]
    assert m["move_bp"] == pytest.approx(-25.0, abs=0.1)
    assert m["stance"] == "cut"


def test_a_late_month_decision_reads_the_next_clean_month() -> None:
    """Oct 27-28: three post-decision days would amplify noise eightfold."""
    pm = meetings_priced(
        rates(3.63, {"2026-10": 3.66, "2026-11": 3.88}),
        [meeting("2026-10-27")],
    )
    (m,) = pm["meetings"]
    assert m["method"] == "clean next month"
    assert m["implied_after"] == pytest.approx(3.88)
    assert m["move_bp"] == pytest.approx(25.0, abs=0.1)


def test_the_clean_month_skips_a_month_with_its_own_meeting() -> None:
    """Back-to-back decisions: November's average is contaminated by the
    December... no — a November contract is clean only if no decision falls in
    November. Here one does, so October's late meeting must read December."""
    pm = meetings_priced(
        rates(3.63, {"2026-10": 3.65, "2026-11": 3.80, "2026-12": 3.90}),
        [meeting("2026-10-27"), meeting("2026-11-17")],
    )
    first = pm["meetings"][0]
    assert first["method"] == "clean next month"
    assert first["implied_after"] == pytest.approx(3.90)


def test_meetings_chain_each_post_is_the_next_pre() -> None:
    sep = (3.63 * 16 + 3.88 * 14) / 30
    dec = (3.88 * 9 + 4.13 * 22) / 31
    pm = meetings_priced(
        rates(3.63, {"2026-09": sep, "2026-12": dec}),
        [meeting("2026-09-15"), meeting("2026-12-08")],
    )
    a, b = pm["meetings"]
    assert a["implied_after"] == pytest.approx(3.88, abs=0.001)
    assert b["move_bp"] == pytest.approx(25.0, abs=0.2)
    assert b["cum_bp"] == pytest.approx(50.0, abs=0.3)


def test_no_effr_anchors_on_the_front_contract_and_says_so() -> None:
    pm = meetings_priced(rates(None, {"2026-09": 3.70, "2026-10": 3.70}), [meeting("2026-09-15")])
    assert pm["anchor_src"] == "front contract"
    assert pm["anchor"] == pytest.approx(3.70)


def test_a_meeting_beyond_the_strip_stops_the_chain() -> None:
    pm = meetings_priced(
        rates(3.63, {"2026-09": 3.70}),
        [meeting("2026-09-15"), meeting("2027-06-15")],
    )
    assert len(pm["meetings"]) == 1


def test_a_month_boundary_meeting_is_dated_by_arithmetic_not_clamping() -> None:
    """Jan 31 + Feb 1 decides on Feb 1, and must read February's numbers."""
    pm = meetings_priced(
        rates(3.63, {"2027-01": 3.63, "2027-02": 3.88, "2027-03": 3.88}),
        [meeting("2027-01-31")],
    )
    (m,) = pm["meetings"]
    assert m["date"] == "2027-02-01"
    # Decided on Feb 1: the new rate holds for nearly all of February, so the
    # own-month un-mixing applies and lands almost exactly on the post rate.
    assert m["move_bp"] == pytest.approx(25.0, abs=1.0)


def test_empty_inputs_return_an_empty_shape_not_an_error() -> None:
    assert meetings_priced({}, []) == {"meetings": [], "anchor": None, "anchor_src": None}
    assert meetings_priced(rates(3.63, {"2026-09": 3.7}), [])["meetings"] == []
