"""
Expiry — the dates that change what the gamma map means.

WHY THIS MATTERS MORE HERE THAN ON AN ORDINARY TERMINAL. The walls this
terminal borrows from GEXYGEN are open-interest structures, and open interest
has a maturity. On the Thursday before a monthly expiry the near book is
enormous and price pins to it; on the Monday after, the same strikes carry
almost nothing and the map is rebuilt around the next cycle. A session note that
does not know it is OpEx week is describing walls without knowing their weight.

NO DATA SOURCE. Every date here is a rule, and rules do not go stale, 404 or
need a key:

  monthly OpEx     the third Friday of each month
  quarterly        the third Friday of Mar / Jun / Sep / Dec — "triple
                   witching", when index futures, index options and stock
                   options all settle together and volume is several times
                   normal
  month end        the last trading day, for the rebalancing flows
  quarter end      the last trading day of Mar / Jun / Sep / Dec

HOLIDAYS ARE HANDLED FOR THE ONES THAT MOVE A FRIDAY. Good Friday is the only
US market holiday that can fall on a third Friday, and when it does the monthly
expiry moves to the Thursday. That is one rule rather than a full holiday
calendar, which this module deliberately does not try to be.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

QUARTER_MONTHS = {3, 6, 9, 12}


def third_friday(year: int, month: int) -> date:
    """The third Friday of a month."""
    d = date(year, month, 1)
    # weekday(): Monday is 0, Friday is 4.
    first_friday = d + timedelta(days=(4 - d.weekday()) % 7)
    return first_friday + timedelta(days=14)


def easter(year: int) -> date:
    """Western Easter Sunday — anonymous Gregorian algorithm.

    Present only because Good Friday is the one US market holiday that can land
    on a third Friday and push a monthly expiry to the Thursday.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def monthly_expiry(year: int, month: int) -> date:
    """The third Friday, moved to Thursday when it is Good Friday."""
    d = third_friday(year, month)
    if d == easter(year) - timedelta(days=2):
        return d - timedelta(days=1)
    return d


def last_trading_day(year: int, month: int) -> date:
    """The last weekday of a month. Holidays are not modelled — none of the
    month-end holidays in the US calendar falls on a last weekday."""
    d = date(year, month, 28)
    while d.month == month:
        nxt = d + timedelta(days=1)
        if nxt.month != month:
            break
        d = nxt
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def upcoming(today: date | None = None, horizon: int = 120) -> list[dict[str, Any]]:
    """Every expiry-shaped date in the next few months, nearest first."""
    t = today or datetime.now(ET).date()
    out: list[dict[str, Any]] = []

    y, m = t.year, t.month
    for _ in range(6):
        exp = monthly_expiry(y, m)
        quarterly = m in QUARTER_MONTHS
        out.append({
            "key": f"opex-{y}-{m:02d}",
            "date": exp.isoformat(),
            "kind": "quarterly" if quarterly else "monthly",
            "label": "Triple witching" if quarterly else "Monthly OpEx",
            "note": (
                "Index futures, index options and stock options settle together — "
                "volume several times normal and the largest open-interest roll of the quarter"
                if quarterly
                else "Monthly options expire; the near book empties and the walls rebuild"
            ),
        })
        eom = last_trading_day(y, m)
        out.append({
            "key": f"eom-{y}-{m:02d}",
            "date": eom.isoformat(),
            "kind": "quarter-end" if quarterly else "month-end",
            "label": "Quarter end" if quarterly else "Month end",
            "note": (
                "Quarter-end rebalancing; pension and index flows concentrate into the close"
                if quarterly
                else "Month-end rebalancing into the close"
            ),
        })
        m += 1
        if m > 12:
            m, y = 1, y + 1

    rows = []
    for r in out:
        d = date.fromisoformat(r["date"])
        days = (d - t).days
        if days < 0 or days > horizon:
            continue
        rows.append({**r, "days": days, "is_today": days == 0})
    rows.sort(key=lambda r: r["days"])
    return rows


def state(today: date | None = None) -> dict[str, Any]:
    """What the calendar means for THIS session, in one object.

    `opex_week` is the claim a session note actually wants: the week containing
    a monthly expiry behaves differently from the three around it, and knowing
    the date alone still leaves that inference to be made.
    """
    t = today or datetime.now(ET).date()
    rows = upcoming(t)
    nxt_opex = next((r for r in rows if r["kind"] in {"monthly", "quarterly"}), None)

    this_month = monthly_expiry(t.year, t.month)
    # Monday of the expiry week through the Friday itself.
    week_start = this_month - timedelta(days=this_month.weekday())
    in_opex_week = week_start <= t <= this_month

    return {
        "today": t.isoformat(),
        "opex_week": in_opex_week,
        "monthly_expiry": this_month.isoformat(),
        "days_to_opex": nxt_opex["days"] if nxt_opex else None,
        "next": rows[:6],
        "note": (
            "OpEx week — the near book is at its largest and price pins to it"
            if in_opex_week
            else None
        ),
    }
