"""
The clock — which desks are trading, and what happens next.

WHY A TERMINAL NEEDS THIS AT ALL. Every number on the board means something
different depending on who is awake to trade it. A 40-handle move in ES at
03:00 ET is London repricing the overnight; the same move at 09:31 is the New
York open and is worth ten times the attention. A board with no session context
is a board that flatters the quietest hours.

EVERYTHING IS COMPUTED IN ET AND CONVERTED, never the reverse. The instruments
here settle on CME and NYSE clocks, both of which are defined in New York time
and observe US daylight saving; deriving from local time would put every
boundary an hour out for three weeks of the year, twice a year, which is
exactly the kind of bug that only shows up when you are least able to spot it.

THE OVERLAPS ARE THE POINT. London-New York, 08:00 to 11:30 ET, is when both
of the two largest pools are open at once and is where the day's range is
usually set. It is called out separately because it is not derivable at a
glance from two rows of open/closed.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# key, label, city zone, local open, local close, weight
#
# `weight` is a coarse liquidity rank used only for ordering and emphasis in
# the UI — New York and London genuinely dominate, and a clock that gives
# Sydney the same visual weight as the NYSE open misinforms.
SESSIONS: list[tuple[str, str, str, time, time, int]] = [
    ("sydney", "Sydney", "Australia/Sydney", time(10, 0), time(16, 0), 1),
    ("tokyo", "Tokyo", "Asia/Tokyo", time(9, 0), time(15, 30), 3),
    ("hongkong", "Hong Kong", "Asia/Hong_Kong", time(9, 30), time(16, 0), 3),
    ("shanghai", "Shanghai", "Asia/Shanghai", time(9, 30), time(15, 0), 2),
    ("london", "London", "Europe/London", time(8, 0), time(16, 30), 5),
    ("frankfurt", "Frankfurt", "Europe/Berlin", time(9, 0), time(17, 30), 3),
    ("newyork", "New York", "America/New_York", time(9, 30), time(16, 0), 5),
]

# The moments inside a US session that reprice things, in ET. Not a calendar —
# these recur every session and are what the next-event countdown runs on.
MARKERS: list[tuple[time, str, str]] = [
    (time(18, 0), "Globex open", "Futures reopen; the new session's first print"),
    (time(2, 0), "London pre-open", "European desks arrive; overnight range often breaks"),
    (time(3, 0), "London open", "Cash equities open in London"),
    (time(8, 0), "London/NY overlap", "Both major pools open — the day's deepest liquidity"),
    (time(8, 30), "US data window", "CPI, PCE, payrolls and claims print at this minute"),
    (time(9, 30), "NYSE open", "US cash equities open"),
    (time(10, 0), "Late data window", "ISM, consumer confidence, JOLTS print at this minute"),
    (time(11, 30), "London close approach", "European desks begin squaring"),
    (time(15, 0), "Final hour", "Closing imbalances begin building"),
    (time(16, 0), "NYSE close", "US cash close; futures continue"),
    (time(17, 0), "CME settlement", "Daily settlement; the futures day rolls"),
]


def _is_weekend(d: datetime) -> bool:
    return d.weekday() >= 5


def _local_window(now_utc: datetime, zone: str, o: time, c: time) -> tuple[datetime, datetime]:
    """Today's open/close for one city, as UTC instants."""
    tz = ZoneInfo(zone)
    local = now_utc.astimezone(tz)
    start = local.replace(hour=o.hour, minute=o.minute, second=0, microsecond=0)
    end = local.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)
    return start.astimezone(UTC), end.astimezone(UTC)


def session_state(
    now_utc: datetime | None = None,
    fed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Who is open, who is next, and how long until each changes."""
    now = now_utc or datetime.now(UTC)
    rows: list[dict[str, Any]] = []

    for key, label, zone, o, c, weight in SESSIONS:
        tz = ZoneInfo(zone)
        local = now.astimezone(tz)
        start, end = _local_window(now, zone, o, c)
        weekend = local.weekday() >= 5
        open_now = (not weekend) and start <= now < end

        if open_now:
            nxt, mins = "closes", (end - now).total_seconds() / 60.0
        else:
            # The next open: today's if it has not happened, else tomorrow's,
            # skipping the weekend. Computed by walking days rather than by
            # arithmetic on weekday numbers, because that walk is obviously
            # correct and the arithmetic is obviously not.
            probe = local
            for _ in range(5):
                cand = probe.replace(hour=o.hour, minute=o.minute, second=0, microsecond=0)
                cand_utc = cand.astimezone(UTC)
                if cand_utc > now and cand.weekday() < 5:
                    break
                probe = probe + timedelta(days=1)
            else:
                cand_utc = now
            nxt, mins = "opens", (cand_utc - now).total_seconds() / 60.0

        rows.append(
            {
                "key": key,
                "label": label,
                "zone": zone,
                "open": open_now,
                "weekend": weekend,
                "local_time": local.strftime("%H:%M"),
                "local_date": local.strftime("%a %d %b"),
                "hours": f"{o.strftime('%H:%M')}–{c.strftime('%H:%M')} local",
                "next": nxt,
                "next_min": round(mins),
                "weight": weight,
            }
        )

    et = now.astimezone(ET)
    et_min = et.hour * 60 + et.minute

    # The overlap. Hard-coded to ET rather than derived from the two rows above
    # because the two cities' DST transitions are three weeks apart and the
    # window genuinely moves during those weeks — a derived value would be
    # right, but nobody could check it.
    overlap = (not _is_weekend(et)) and (8 * 60) <= et_min < (11 * 60 + 30)

    return {
        "et": et.isoformat(),
        "et_time": et.strftime("%H:%M:%S"),
        "et_date": et.strftime("%a %d %b %Y"),
        "utc": now.isoformat(),
        "weekend": _is_weekend(et),
        "sessions": rows,
        "open_count": sum(1 for r in rows if r["open"]),
        "overlap": overlap,
        "phase": _phase(et, rows),
        "markers": _markers(et, fed),
    }


# Which desks make an overnight phase. New York is deliberately absent: its
# sub-phases are finer than open/closed and come from the ET ladder instead.
_ASIA = {"sydney", "tokyo", "hongkong", "shanghai"}
_EUROPE = {"london", "frankfurt"}


def _phase(et: datetime, rows: list[dict[str, Any]]) -> dict[str, str]:
    """
    The one-line answer to "where are we in the day".

    HALF BUCKETED, HALF DERIVED, and the split is the whole design.

    New York's sub-phases — pre-open, morning, midday, final hours, post-close —
    are finer than open/closed, and they are defined in ET, which IS New York's
    own clock. A fixed ET ladder is exactly right for them and cannot drift.

    ASIA AND LONDON ARE NOT DEFINED IN ET, and bucketing them by it was wrong
    twice over. It read "Globex" from 18:00 ET to midnight, which is most of the
    Asian session: observed 2026-08-31 at 20:51 ET with Sydney and Tokyo both
    marked OPEN in the very rows printed under a label claiming no cash market
    was trading. The panel was contradicting itself on its own face.

    And a merely corrected bucket could not have stayed right. Sydney keeps
    southern-hemisphere DST while New York keeps northern, so Sydney's open
    swings between 18:00 and 20:00 ET across the year and the two zones change
    on four different dates. Any ET constant for it is wrong for part of every
    year. The module docstring's rule — compute in ET, never the reverse — is
    sound for the CME and NYSE boundaries it was written about, because those
    ARE defined in New York time; it does not transfer to Tokyo.

    So the overnight phases are read off `rows`, which already resolve each city
    in its own zone against its own local weekday. One computation now feeds
    both the headline and the list beneath it, so they cannot disagree again.
    """
    wd = et.weekday()
    m = et.hour * 60 + et.minute

    # THE WEEK IS BOUNDED BY GLOBEX, NOT BY THE CALENDAR. Futures shut 17:00 ET
    # Friday and reopen 18:00 ET Sunday, so a plain `weekday() >= 5` called
    # Sunday evening "Weekend" while the new week's first prints were already on
    # the tape. That is not a corner case for this desk: 18:00 ET Sunday is
    # 08:00 Monday in Sydney, i.e. the start of its actual working week.
    if wd == 5 or (wd == 6 and m < 18 * 60) or (wd == 4 and m >= 17 * 60):
        return {"key": "weekend", "label": "Weekend", "note": "Futures reopen Sunday 18:00 ET"}

    # New York, in New York's own clock.
    if 8 * 60 <= m < 9 * 60 + 30:
        return {"key": "preopen", "label": "US pre-open", "note": "Data window and the overlap"}
    if 9 * 60 + 30 <= m < 11 * 60 + 30:
        return {"key": "open", "label": "NY morning", "note": "Deepest liquidity of the day"}
    if 11 * 60 + 30 <= m < 14 * 60:
        return {"key": "midday", "label": "NY midday", "note": "Volume typically troughs"}
    if 14 * 60 <= m < 16 * 60:
        return {"key": "close", "label": "NY final hours", "note": "Imbalances and positioning"}
    if 16 * 60 <= m < 18 * 60:
        return {"key": "post", "label": "Post-close", "note": "Cash shut; settlement at 17:00 ET"}

    # Overnight: whoever is actually trading says what this is.
    live = {r["key"] for r in rows if r.get("open")}
    asia = bool(live & _ASIA)
    europe = bool(live & _EUROPE)

    if asia and europe:
        return {
            "key": "handover",
            "label": "Asia into London",
            "note": "Hong Kong still trading as Europe arrives",
        }
    if europe:
        return {
            "key": "london",
            "label": "London session",
            "note": "Europe repricing the overnight",
        }
    if asia:
        return {"key": "asia", "label": "Asia session", "note": "Tokyo and Hong Kong lead"}
    return {"key": "globex", "label": "Globex", "note": "Futures only; no cash market open"}


# The Fed releases that land AT A MINUTE and stop the tape, keyed by the
# calendar's own `kind`. Speeches are scheduled too, but they run for an hour
# and belong in the Fed diary rather than on the session clock.
_FED_MARKERS: dict[str, str] = {
    "FOMC": "Rate decision and the statement land at this minute",
    "Beige Book": "The Fed's regional survey lands at this minute",
}


def _fed_markers(et: datetime, fed: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Today's scheduled Fed releases, as session-clock moments.

    THIS REPLACES A DAILY "FOMC HOUR" MARKER, which sat at 14:00 ET every day of
    the year whether or not the committee was meeting. It read as "the FOMC is
    today" on the ~350 days a year when it was not — the reader has no way to
    tell a recurring clock landmark from a real event, and should not have to.
    Now the marker exists only when the Board's calendar says it does, and it
    carries the event's OWN time rather than an assumed 14:00.
    """
    today = et.date().isoformat()
    out: list[dict[str, Any]] = []
    for e in fed or []:
        note = _FED_MARKERS.get(str(e.get("kind") or ""))
        if note is None or e.get("date") != today or not e.get("et"):
            continue
        hh, _, mm = str(e["et"]).partition(":")
        try:
            cand = datetime.combine(et.date(), time(int(hh), int(mm)), tzinfo=ET)
        except ValueError:
            continue
        if cand <= et:
            continue  # Already landed. The wire has it now.
        title = str(e.get("title") or e.get("kind") or "").strip()
        out.append(
            {
                "label": title if e.get("kind") == "FOMC" else str(e.get("kind")),
                "note": note,
                "et": cand.strftime("%H:%M"),
                "in_min": round((cand - et).total_seconds() / 60.0),
            }
        )
    return out


def _markers(et: datetime, fed: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The next few session moments, with minutes to each."""
    today = et.date()
    out: list[dict[str, Any]] = _fed_markers(et, fed)
    for t, label, note in MARKERS:
        cand = datetime.combine(today, t, tzinfo=ET)
        if cand <= et:
            cand += timedelta(days=1)
        out.append(
            {
                "label": label,
                "note": note,
                "et": cand.strftime("%H:%M"),
                "in_min": round((cand - et).total_seconds() / 60.0),
            }
        )
    out.sort(key=lambda r: r["in_min"])
    return out[:4]
