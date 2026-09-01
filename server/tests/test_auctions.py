"""
The auction diary's rules, pinned.

Two are silently invertible: a reopening labelled by its residual term
("9-Year 11-Month") instead of what the market calls it, and the bill flood —
most of the feed — drowning the three coupon auctions that matter.
"""

from __future__ import annotations

from datetime import date

from newsterminal.sources.auctions import parse

TODAY = date(2026, 9, 1)


def row(**kw) -> dict:
    base = {
        "securityType": "Note",
        "securityTerm": "10-Year",
        "originalSecurityTerm": "10-Year",
        "reopening": "No",
        "auctionDate": "2026-09-09T00:00:00",
        "offeringAmount": "",
    }
    return {**base, **kw}


def test_bills_and_frns_are_dropped_coupons_kept() -> None:
    rows = parse(
        [
            row(securityType="Bill", securityTerm="4-Week"),
            row(securityType="FRN", securityTerm="2-Year"),
            row(securityType="CMB", securityTerm="42-Day"),
            row(),
            row(securityType="Bond", securityTerm="30-Year", auctionDate="2026-09-10T00:00:00"),
        ],
        TODAY,
    )
    assert [r["label"] for r in rows] == ["10Y", "30Y"]


def test_a_reopening_is_named_what_the_market_calls_it() -> None:
    (r,) = parse(
        [row(securityTerm="9-Year 11-Month", originalSecurityTerm="10-Year", reopening="Yes")],
        TODAY,
    )
    assert r["label"] == "10Y"
    assert r["reopening"] is True


def test_the_long_end_is_major_and_the_belly_is_not() -> None:
    rows = parse(
        [
            row(securityTerm="3-Year", auctionDate="2026-09-08T00:00:00"),
            row(),
            row(securityType="Bond", securityTerm="30-Year", auctionDate="2026-09-10T00:00:00"),
            row(securityType="TIPS", securityTerm="10-Year", auctionDate="2026-09-11T00:00:00"),
        ],
        TODAY,
    )
    by = {r["label"]: r for r in rows}
    assert by["3Y"]["major"] is False
    assert by["10Y"]["major"] is True
    assert by["30Y"]["major"] is True
    # TIPS supply is real but does not move the nominal long end the same way.
    assert by["10Y TIPS"]["major"] is False


def test_amounts_appear_only_once_announced() -> None:
    a, b = parse(
        [row(offeringAmount="42000000000"), row(auctionDate="2026-09-10T00:00:00")],
        TODAY,
    )
    assert a["amount_bn"] == 42.0
    assert b["amount_bn"] is None


def test_past_auctions_and_junk_terms_stay_out() -> None:
    rows = parse(
        [
            row(auctionDate="2026-08-28T00:00:00"),
            row(securityTerm="not-a-term", originalSecurityTerm=""),
            row(auctionDate="garbage"),
        ],
        TODAY,
    )
    assert rows == []


def test_the_close_is_one_pm_eastern() -> None:
    (r,) = parse([row()], TODAY)
    assert r["et"] == "13:00"
    assert r["utc"].startswith("2026-09-09T17:00")  # EDT in September
