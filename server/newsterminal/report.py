"""
The session report — a model reads the whole terminal and calls a bias.

OWNER'S DECISION, 2026-08-31: THE MODEL DOES THE ANALYSIS. The alternative on
the table was a scored rules engine that decides the bias deterministically and
cites the arithmetic behind every line, with the model used only to narrate it.
The owner chose the model-forms-the-view version knowing the trade: two runs on
identical data can disagree, and there is no arithmetic to audit when it is
wrong. That is recorded here rather than argued again.

WHAT IS DONE ANYWAY, BECAUSE IT COSTS NOTHING AND MAKES THE CALL CHECKABLE:

  1. The model is handed a CURATED DIGEST, not the raw snapshot. 250 KB of
     per-strike maps and 300 headlines would bury the signal and cost a fortune
     in tokens; ~2 kB of the figures a desk would actually read does not. What
     goes in is decided here, in `build_digest`, where it can be reviewed.
  2. Every report is STAMPED with the model, the moment, and the digest it saw.
     A bias you cannot reproduce is a bias you cannot learn from, so the inputs
     are stored beside the output.
  3. The output is a STRUCTURED OBJECT, not prose. A schema means the panel
     renders fields rather than regexing paragraphs, and it forces the model to
     commit to a direction and a conviction instead of hedging in adjectives.
  4. Reports are KEPT. The one you took at 09:00 is still there at 15:00, which
     is the only way to find out whether the calls are any good.

NO KEY, NO REPORT. There is deliberately no fallback that fabricates a bias
locally — a made-up view presented in the same panel as a real one is exactly
the failure this project's sister README calls the worst thing it could do.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .config import CACHE_DIR, UA

ET = ZoneInfo("America/New_York")

OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

# Free on OpenRouter and one of only a handful of free models that support
# `structured_outputs`, which the schema below depends on. Overridable because
# the free roster changes month to month.
DEFAULT_MODEL = os.environ.get("NT_REPORT_MODEL", "z-ai/glm-5.2:free")

# ---------------------------------------------------------------------------
# THE FALLBACK CHAIN, AND WHY A SINGLE FREE MODEL ID IS NOT ENOUGH.
#
# A `:free` variant does not get its own capacity — it routes to a provider
# pool shared by every OpenRouter user on that model, and when the pool is
# saturated the request comes back 429 with `upstream_provider_shared_pool`. It
# is not our quota, retrying does not help, and it lasts as long as it lasts:
# the very first report generated on this desk hit it four times in a row.
#
# So the model is a LIST rather than a value. The configured model is tried
# first and the rest are tried in order, and the report records which one
# actually answered — a note written by the second choice must say so, because
# "which model wrote this" is half the provenance.
#
# Every entry supports `structured_outputs`, which is not optional here: the
# schema is what makes the model commit to a direction instead of hedging, and
# a model without it would return prose the panel cannot render.
FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "dots-studio/dots-3-note-preview:free",
]

# Statuses worth trying again for. A 401 is the key and no other model will fix
# it; a 400 outside strict-schema mode is our request and moving on would hide
# it behind a different model's answer.
#
# 404 IS IN HERE, WHICH LOOKS WRONG AND IS NOT. The free Nvidia endpoint returns
# 404 intermittently for identical requests — measured with
# `server/tools/budget_probe.py`: max_tokens 200 gave 404, 3000 succeeded, 4000
# succeeded, 8000 gave "Service temporarily unavailable". It is not a route that
# does not exist and it is not a budget ceiling; it is a shared free endpoint
# falling over. Treating it as fatal ended the whole chain on a coin flip.
RETRYABLE = {404, 408, 425, 429, 500, 502, 503, 504}

# Provider-level wobbles that arrive as a 200 with an `error` body rather than
# as a status code.
TRANSIENT_TEXT = re.compile(
    r"temporarily|rate.?limit|unavailable|overload|capacity|try again|timeout",
    re.I,
)

# Tries per (model, mode) pair before moving on, and the ceiling on the lot.
# The failures above are intermittent, so one extra try converts most of them;
# the cap stops a bad afternoon turning one press of Generate into thirty
# requests against a free quota.
TRIES_PER_PAIR = 2
MAX_ATTEMPTS = 10

# A WALL-CLOCK CEILING, because the attempt count alone does not bound anything.
#
# Ten attempts at up to ninety seconds each is fifteen minutes, and a GC report
# generated during a saturated afternoon ran past the route handler's own 290s
# timeout — the browser gave up on a generation the collector was still paying
# for. Attempts are only STARTED while there is budget left, so the last one
# can still overrun by its own timeout; 210 plus a 70s request fits inside the
# route's window with room to return the failure.
BUDGET_SEC = 210.0
REQUEST_TIMEOUT_SEC = 70

# What one attempt is assumed to cost when deciding whether to start another.
#
# Larger than REQUEST_TIMEOUT_SEC on purpose. That constant is passed to
# `urlopen`, whose timeout applies to each socket operation rather than to the
# request as a whole, so a response that arrives slowly but steadily can run
# far past it — observed at ~150s per attempt against a saturated free pool
# while the socket option said 70. This is the figure the budget reserves, so
# the endpoint's worst case is roughly BUDGET_SEC rather than BUDGET_SEC plus
# one unbounded request.
_ATTEMPT_RESERVE = 90.0


def model_chain(preferred: str) -> list[str]:
    """The configured model first, then the others, without duplicates."""
    chain = [preferred]
    chain.extend(m for m in FALLBACK_MODELS if m != preferred)
    return chain

REPORTS_DIR = os.path.join(CACHE_DIR, "reports")
KEEP = 40


def _key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


# --------------------------------------------------------------------------
# The digest — what the model is allowed to see.
# --------------------------------------------------------------------------


def _q(quotes: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next((q for q in quotes if q.get("key") == key), None)


def _brief(q: dict[str, Any] | None) -> dict[str, Any] | None:
    """One instrument, trimmed to what a read actually uses."""
    if not q:
        return None
    out: dict[str, Any] = {
        "last": q.get("last"),
        "pct": round(q["pct"], 2) if q.get("pct") is not None else None,
    }
    if q.get("range_pos") is not None:
        # Where in the day's range the last print sits — the figure that says
        # whether a gain is being held or given back.
        out["day_range_pos"] = round(q["range_pos"], 2)
    if q.get("high") is not None and q.get("low") is not None:
        out["day_high"], out["day_low"] = q["high"], q["low"]
    return out


# --------------------------------------------------------------------------
# Which session the note is for.
#
# THIS DESK TRADES THREE OF THEM. A note written for the New York open is the
# wrong note at 20:00 ET when Tokyo is about to go, and the difference is not
# cosmetic: the instruments that lead are different, the calendar is different,
# the liquidity is different, and what "overnight" even refers to inverts. So
# the session is a parameter, `auto` resolves it from the ET clock, and the
# prompt below is assembled around whichever one is chosen.
# --------------------------------------------------------------------------

SESSIONS: dict[str, dict[str, str]] = {
    "asia": {
        "label": "Asia",
        "hours": "18:00–03:00 ET (Tokyo 19:00–01:00, Hong Kong 21:30–04:00)",
        "leads": "Nikkei, Hang Seng, Shanghai, KOSPI, ASX; USD/JPY, AUD/USD, USD/CNY",
        "handover": "New York's close is the handover — Asia opens reacting to it",
        "character": (
            "Thinner than New York. Index futures often range unless a regional print or "
            "a policy headline moves them, and USD/JPY tends to lead the Nasdaq future "
            "rather than follow it. Gamma walls hold more easily in thin liquidity."
        ),
    },
    "london": {
        "label": "London",
        "hours": "03:00–08:00 ET (London cash 03:00–11:30 ET)",
        "leads": "FTSE, DAX, Euro Stoxx; EUR/USD, GBP/USD, Bunds and Gilts",
        "handover": "Asia's session is the handover — London reprices what Asia did",
        "character": (
            "The first real liquidity of the day. London routinely takes out the Asia "
            "high or low and either extends or reverses it, so where price sits against "
            "the Asia range is the single most useful fact at 03:00."
        ),
    },
    "ny": {
        "label": "New York",
        "hours": "09:30–16:00 ET, with the 08:00–11:30 London overlap around the open",
        "leads": "NQ/ES/YM/RTY, the sector SPDRs, the Treasury curve, the dollar",
        "handover": "Asia and London are the handover — the US opens into their range",
        "character": (
            "The deepest liquidity and the widest ranges. The 08:30 data window and the "
            "09:30 open set the day; dealer gamma matters most here because the option "
            "volume that creates it is American."
        ),
    },
}


# --------------------------------------------------------------------------
# Which book the note is about.
#
# `all` is the default and covers the three together, which is the right note
# when you are deciding what to trade. The single-asset choices are for when
# you have already decided: they narrow the gamma, the session ranges and the
# index movers to that instrument and tell the model what drives it.
#
# GOLD IS NOT A THIRD EQUITY INDEX, and the `drivers` line is where that is
# said. Sector rotation and index constituents explain NQ and ES and explain
# nothing about GC — real rates, the dollar and geopolitics do. A single-asset
# note that dutifully worked through XLK's relative strength on the way to a
# gold call would be padding at best.
# --------------------------------------------------------------------------

# Which quotes ARE each book, as opposed to context for it. Kept beside ASSETS
# so the focus split and the prose describing it cannot drift apart.
BOOK_KEYS: dict[str, tuple[str, ...]] = {
    "NQ": ("NQ_futures", "QQQ"),
    "ES": ("ES_futures", "SPY"),
    "GC": ("GC_gold_futures", "GLD"),
}

ASSETS: dict[str, dict[str, str]] = {
    "all": {
        "label": "All three books",
        "instruments": "NQ/QQQ, ES/SPY and GC/GLD",
        "drivers": (
            "Cover all three. Say where they agree and, more usefully, where they do not — "
            "equities and gold diverging is itself the read."
        ),
    },
    "NQ": {
        "label": "NQ",
        "instruments": "NQ futures and QQQ",
        "drivers": (
            "The Nasdaq 100 is cap-weighted and its top handful of names are about 43% of it, "
            "so `index_movers` usually IS the story. It is the longest-duration equity index, "
            "so the front of the curve and the policy path hit it hardest. Technology's "
            "relative strength matters more here than the rest of the sector table."
        ),
    },
    "ES": {
        "label": "ES",
        "instruments": "ES futures and SPY",
        "drivers": (
            "Broader than the Nasdaq, so sector rotation carries more of the explanation and "
            "no single name dominates the way it does in NQ. Breadth — equal weight against "
            "cap weight — says whether a move is the whole market or the top of it."
        ),
    },
    "GC": {
        "label": "GC",
        "instruments": "GC futures and GLD",
        "drivers": (
            "Gold is NOT an equity index and the equity blocks mostly do not apply to it. "
            "What moves it: real yields and the policy path, the dollar, and geopolitical "
            "risk. Ignore sector rotation and index constituents unless equities are moving "
            "hard enough to be a risk signal in their own right."
        ),
    },
}


def resolve_asset(want: str) -> str:
    return want if want in ASSETS else "all"


def resolve_session(clock: dict[str, Any], want: str = "auto") -> str:
    """Which session a note is being written for.

    `auto` resolves to the session that is about to trade or is trading now,
    which is what someone pressing Generate almost always means. Between 16:00
    and 18:00 ET nothing is open and the honest answer is the one that reopens.
    """
    if want in SESSIONS:
        return want
    et = str(clock.get("et") or "")
    try:
        hour = int(et[11:13]) + int(et[14:16]) / 60.0
    except (ValueError, IndexError):
        return "ny"
    if 16.0 <= hour < 18.0 or hour >= 18.0 or hour < 2.0:
        return "asia"
    if 2.0 <= hour < 7.5:
        return "london"
    return "ny"


def build_digest(
    snap: dict[str, Any], session: str = "ny", asset: str = "all"
) -> dict[str, Any]:
    """The terminal, compressed to the facts a desk would read out loud."""
    quotes = snap.get("quotes") or []
    clock = snap.get("clock") or {}
    rates = snap.get("rates") or {}
    sectors = snap.get("sectors") or []
    cal = snap.get("calendar") or []
    wire = snap.get("wire") or []
    gex = (snap.get("gex") or {}).get("assets") or {}

    now_ts = time.time()

    # THE BLOCK NAMES CARRY THE SCOPE, because a structure is obeyed where an
    # instruction is only read. Told in prose to write about NQ but handed eight
    # instruments in one block called `the_book`, the model treated all eight as
    # the subject and returned gold and ES calls inside a note the reader had
    # scoped to NQ. Splitting the block makes the wrong answer harder to write
    # than the right one. The context stays — NQ leading ES is a genuine read —
    # but it can no longer be mistaken for the thing being traded.
    all_books: dict[str, Any] = {
        "NQ_futures": _brief(_q(quotes, "NQ")),
        "QQQ": _brief(_q(quotes, "QQQ")),
        "ES_futures": _brief(_q(quotes, "ES")),
        "SPY": _brief(_q(quotes, "SPY")),
        "GC_gold_futures": _brief(_q(quotes, "GC")),
        "GLD": _brief(_q(quotes, "GLD")),
        "YM_dow": _brief(_q(quotes, "YM")),
        "RTY_russell": _brief(_q(quotes, "RTY")),
    }
    focus_keys = BOOK_KEYS.get(asset, ())
    if focus_keys:
        book: dict[str, Any] = {
            "the_book_this_note_is_about": {k: all_books[k] for k in focus_keys},
            "other_books_context_only": {
                k: v for k, v in all_books.items() if k not in focus_keys
            },
        }
    else:
        # All three books are the subject, so there is nothing to hold back.
        book = {"the_book": all_books}

    # ONE PLACE DECIDES WHAT "FOCUSED" MEANS, so the three per-instrument
    # blocks cannot disagree about which book the note is for.
    def wanted(key: str) -> bool:
        return asset == "all" or key == asset

    # ---- gamma: the seven levels per asset, with spot placed among them ----
    gamma: dict[str, Any] = {}
    for name, v in gex.items():
        if not v.get("ok") or not wanted(name):
            continue
        gamma[name] = {
            "spot": v.get("spot"),
            "regime": v.get("regime"),
            "regime_means": (
                "dealer hedging dampens moves; expect mean reversion between walls"
                if v.get("regime") == "POS"
                else "dealer hedging amplifies moves; expect trend and range extension"
            ),
            "levels": [
                {
                    "label": lv["label"],
                    "price": lv["price"],
                    "distance_pct": (
                        round(lv["dist_pct"], 2) if lv.get("dist_pct") is not None else None
                    ),
                }
                for lv in (v.get("levels") or [])
            ],
        }

    # ---- sectors: the ends of the ranking, not all thirteen ---------------
    movable = [
        s for s in sectors
        if s.get("key") not in {"SPY", "RSP"} and s.get("rs_day") is not None
    ]
    ranked = sorted(movable, key=lambda s: -(s["rs_day"]))
    rsp = next((s for s in sectors if s.get("key") == "RSP"), None)

    # ---- calendar: what is still to come today, plus what just printed ----
    ahead = [
        {
            "et": r.get("et"),
            "country": r.get("country"),
            "event": r.get("event"),
            # Which trading session the print lands in — an Asia note cares
            # about the 21:30 ET GDP in a way a NY note does not.
            "lands_in_session": r.get("session"),
            "consensus": r.get("consensus_raw"),
            "previous": r.get("previous_raw"),
            "impact": r.get("score"),
        }
        for r in cal
        if not r.get("released") and (r.get("ts") or 0) >= now_ts and (r.get("score") or 0) >= 3
    ][:10]
    printed = [
        {
            "et": r.get("et"),
            "country": r.get("country"),
            "event": r.get("event"),
            "actual": r.get("actual_raw"),
            "consensus": r.get("consensus_raw"),
            "surprise": round(r["surprise"], 2) if r.get("surprise") is not None else None,
        }
        for r in sorted(
            [r for r in cal if r.get("released") and (r.get("score") or 0) >= 3],
            key=lambda r: -(r.get("ts") or 0),
        )
    ][:8]

    # ---- the wire ----------------------------------------------------------
    #
    # WEIGHTED TO THE SESSION BEING TRADED. For an Asia note, an item from
    # Nikkei Asia or the RBA is worth more than a US market wrap, and the
    # reverse holds at 09:00 ET. Regional items for the session come first, the
    # rest follow, and nothing is dropped for being from the wrong desk — a
    # strike on a refinery is an Asia story too.
    # Sets, because a session can have more than one home region: London's
    # tape is the UK's AND the euro area's — with only "eu" here, the Bank of
    # England ranked as foreign news in a London note.
    homes = {
        "asia": {"apac", "global"},
        "london": {"uk", "eu", "global"},
        "ny": {"us", "global"},
    }.get(session, {"us", "global"})
    material = [h for h in wire if h.get("impact") in {"high", "medium"}]
    local = [h for h in material if h.get("region") in homes]
    rest = [h for h in material if h.get("region") not in homes]
    heads = [
        {
            "time_et": (h.get("utc") or "")[11:16],
            "impact": h.get("impact"),
            "desk": h.get("category"),
            "region": h.get("region"),
            "publisher": h.get("publisher"),
            "title": h.get("title"),
        }
        for h in [*local[:24], *rest[:8]]
    ]

    # ---- what each session actually did ------------------------------------
    ranges = {}
    for name, v in ((snap.get("ranges") or {}).get("assets") or {}).items():
        if not wanted(name):
            continue
        ranges[name] = {
            "last": v.get("last"),
            "sessions": [
                {
                    "session": r["label"],
                    "high": r["high"],
                    "low": r["low"],
                    "range": round(r["range"], 1) if r.get("range") is not None else None,
                    "change_pct": round(r["chg_pct"], 2) if r.get("chg_pct") is not None else None,
                    # 0 at that session's low, 1 at its high, >1 means the
                    # current price has taken the session's high out.
                    "where_price_sits": round(r["pos"], 2) if r.get("pos") is not None else None,
                }
                for r in (v.get("sessions") or [])
                if r.get("ok")
            ],
        }

    return {
        "writing_for_session": SESSIONS.get(session, SESSIONS["ny"])["label"],
        "session_hours": SESSIONS.get(session, SESSIONS["ny"])["hours"],
        "writing_about": ASSETS[resolve_asset(asset)]["instruments"],
        "as_of_et": clock.get("et"),
        "session_phase": (clock.get("phase") or {}).get("label"),
        "sessions_open": [s["label"] for s in (clock.get("sessions") or []) if s.get("open")],
        "london_ny_overlap": clock.get("overlap"),
        "next_session_events": [
            {"event": m["label"], "et": m["et"], "in_minutes": m["in_min"]}
            for m in (clock.get("markers") or [])[:3]
        ],
        **book,
        "overnight_sessions": {
            k: _brief(_q(quotes, k))
            for k in ("N225", "HSI", "SHCOMP", "FTSE", "DAX", "SX5E")
        },
        "volatility": {k: _brief(_q(quotes, k)) for k in ("VIX", "VVIX", "MOVE", "VXN")},
        # THE SHAPE, NOT JUST THE LEVEL. Contango is the calm shape; the near
        # tenor overtaking the far one is the stressed one, and that crossover
        # usually leads the index rather than following it.
        "vol_term_structure": snap.get("volterm") or {},
        # Coupon supply. A tailed 10s or 30s auction reprices the long end at
        # 13:01 ET, and the longest-duration equity index moves with it.
        "treasury_supply_ahead": [
            {
                "date": a.get("date"),
                "closes_et": a.get("et"),
                "tenor": a.get("label"),
                "amount_bn": a.get("amount_bn"),
                "reopening": a.get("reopening"),
                "in_days": a.get("in_days"),
            }
            for a in (snap.get("auctions") or [])[:6]
        ],
        # Scheduled Fed risk. The headlines block carries what has been said;
        # this is what is about to be.
        "fed_ahead": [
            {
                "date": e.get("date"),
                "et": e.get("et"),
                "kind": e.get("kind"),
                "what": e.get("title"),
                "in_days": e.get("in_days"),
            }
            for e in (snap.get("fed") or [])[:8]
        ],
        "rates": {
            "effr": (rates.get("policy") or {}).get("EFFR", {}).get("rate"),
            "curve": {r["key"]: {"yield": r["value"], "chg_bp": r.get("chg_bp")}
                      for r in (rates.get("curve") or [])},
            "spreads": {r["label"]: f"{r['value']}{r.get('unit', '')}"
                        for r in (rates.get("spreads") or [])},
            "policy_path": rates.get("path") or {},
            # Per-meeting, chained from EFFR: WHICH decision carries the move.
            # "+59bp by October" and "+16bp on Sep 16, +7bp on Oct 28" are
            # different notes, and only the second can be wrong-footed by one
            # speech.
            "fomc_meetings_priced": [
                {
                    "decision": m.get("date"),
                    "priced_bp": m.get("move_bp"),
                    "stance": m.get("stance"),
                    "implied_after_pct": m.get("implied_after"),
                }
                for m in (snap.get("policy_meetings") or {}).get("meetings") or []
            ][:6],
        },
        "dollar_and_commodities": {
            k: _brief(_q(quotes, k))
            for k in ("DXY", "USDJPY", "WTI", "BRENT", "NATGAS", "SILVER", "COPPER")
        },
        "risk_appetite": {k: _brief(_q(quotes, k)) for k in ("BTC", "HYG", "TLT")},
        "gamma_levels": gamma,
        # What each session traded, and where price sits inside each range.
        # The most useful block on the page for a handover read: "London has
        # already taken out the Asia high" is one number here and an inference
        # from four elsewhere.
        "session_ranges": ranges,
        "expiry": snap.get("expiry") or {},
        "earnings": [
            {
                "symbol": e.get("symbol"),
                "name": e.get("name"),
                "date": e.get("date"),
                "when": e.get("when"),
                "eps_forecast": e.get("eps_forecast"),
                "eps_actual": e.get("eps_actual"),
            }
            for e in (snap.get("earnings") or [])[:14]
        ],
        # WHAT ACTUALLY MOVED THE INDEX, name by name. The rotation block
        # says which sectors are being bought; this says which individual
        # weights supplied today's move, which on a cap-weighted index is
        # usually two or three names and is a different question.
        "index_movers": {
            k: {
                "covered_weight_pct": v.get("covered_weight"),
                "net_contribution_pct": v.get("net_contribution"),
                "biggest": [
                    {
                        "symbol": m["symbol"],
                        "weight_pct": m["weight"],
                        "change_pct": m["pct"],
                        "index_points_pct": m["contribution"],
                    }
                    for m in (v.get("members") or [])[:8]
                ],
            }
            for k, v in ((snap.get("constituents") or {}).get("indices") or {}).items()
            if wanted(k)
        },
        "sector_rotation_1d_vs_spy": {
            "leading": [
                {"sector": s["label"], "rs_pct": round(s["rs_day"], 2)} for s in ranked[:4]
            ],
            "lagging": [
                {"sector": s["label"], "rs_pct": round(s["rs_day"], 2)} for s in ranked[-4:]
            ],
            "breadth_rsp_vs_spy_pct": round(rsp["rs_day"], 2)
            if rsp and rsp.get("rs_day") is not None
            else None,
        },
        "calendar_ahead_today": ahead,
        "calendar_just_printed": printed,
        "headlines": heads,
    }


# --------------------------------------------------------------------------
# The schema. Forces a direction and a conviction rather than adjectives.
# --------------------------------------------------------------------------

BIASES = ("bullish", "leaning bullish", "neutral", "leaning bearish", "bearish")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "bias", "conviction", "headline", "summary", "drivers",
        "invalidation", "session_expectation", "levels_to_watch", "risks",
    ],
    "properties": {
        "bias": {
            "type": "string",
            "enum": list(BIASES),
        },
        "conviction": {"type": "integer", "minimum": 1, "maximum": 5},
        "headline": {"type": "string", "description": "One line, under 100 characters."},
        "summary": {"type": "string", "description": "Two or three sentences."},
        "drivers": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["point", "evidence", "direction"],
                "properties": {
                    "point": {"type": "string"},
                    "evidence": {
                        "type": "string",
                        "description": "The specific figures from the data that support this.",
                    },
                    "direction": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                },
            },
        },
        "invalidation": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["condition", "flips_to"],
                "properties": {
                    "condition": {"type": "string"},
                    "flips_to": {"type": "string"},
                },
            },
        },
        "session_expectation": {
            "type": "string",
            "description": "How the session is expected to behave: trend, chop, range, "
                           "squeeze, and where the action is likely to sit.",
        },
        "levels_to_watch": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["instrument", "level", "why"],
                "properties": {
                    "instrument": {"type": "string"},
                    "level": {"type": "string"},
                    "why": {"type": "string"},
                },
            },
        },
        "risks": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "string"}},
    },
}

def system_prompt(session: str, asset: str = "all") -> str:
    """The instructions, assembled around the session AND the book being traded.

    ONE PROMPT PER COMBINATION RATHER THAN ONE GENERIC ONE. A note that says
    "the open" without saying which open is describing nothing, and a model
    given a New York framing will reach for the Fed and the sector tape at
    20:00 ET when the reader is about to trade the Nikkei. The same holds for
    the instrument: told to write about gold, a model handed the equity blocks
    will work through technology's relative strength on the way to a call that
    has nothing to do with it. Both blocks below name what actually drives the
    thing being written about.
    """
    s = SESSIONS.get(session, SESSIONS["ny"])
    a = ASSETS[resolve_asset(asset)]

    # THE MUST-READ LIST BENDS WITH THE BOOK, because the fixed one contradicted
    # the asset drivers. GC's drivers said "ignore sector rotation and index
    # constituents" while the static list three paragraphs later ordered both to
    # "appear somewhere in the note" — two instructions pulling opposite ways in
    # one prompt, resolved by whichever the model happened to weight. Worse, a
    # GC digest carries an EMPTY index_movers block (constituents are filtered
    # to the asset, and gold has none), so the old rule demanded a citation from
    # a block with nothing in it.
    #
    # The rotation ARITHMETIC never changes — eleven S&P sectors against their
    # own aggregate is one market-wide fact. What changes per book is whether
    # that fact is structure or weather: for ES it is the internal composition
    # of the thing being traded, for NQ it is mostly one row (technology's
    # relative strength), and for gold it is an equity risk signal at most.
    if resolve_asset(asset) == "GC":
        must_read = """\
  session_ranges   what each session traded, and where price sits inside each. \
The most important block for a handover: 0 is that session's low, 1 its high, \
above 1 means the high has been taken out.
  gamma_levels     where dealer hedging turns on the GC board, and the regime.
  rates            the policy path and the curve. Real yields are the carrying \
cost of a zero-coupon asset, so gold trades the front of the curve and what is \
priced into it.
  dollar_and_commodities   the unit gold is priced in, plus silver and copper — \
which say whether a metals move is monetary or industrial.

Then volatility, the calendar ahead, expiry and the headlines — context, cited \
where it changes the read. Sector rotation and index constituents are equity \
internals: bring them in only when equities are moving hard enough to be a risk \
signal for gold in their own right, never as structure."""
    else:
        must_read = """\
  session_ranges   what each session traded, and where price sits inside each. \
The most important block for a handover: 0 is that session's low, 1 its high, \
above 1 means the high has been taken out.
  gamma_levels     where dealer hedging turns, and the regime.
  index_movers     WHICH NAMES supplied the move. These indices are \
cap-weighted and two or three names are usually the day, so "NQ is down" and \
"NQ is down because AMZN is off 2.5%" are different notes. Use the contribution \
figures, which are weight times return — not the raw percent changes.
  sector_rotation  WHICH SECTORS are being bought, as excess return over SPY. \
Defensives leading is a different tape from technology leading.

Then rates and the policy path, volatility, the dollar and commodities, the \
calendar ahead, earnings, expiry and the headlines — context, cited where it \
changes the read."""

    return f"""You are a markets strategist writing the session note for one \
trader's desk. They trade NQ/QQQ, ES/SPY and GC/GLD futures and ETFs, and they \
trade the Asia, London and New York sessions.

THIS NOTE IS ABOUT {a["instruments"].upper()}.
  {a["drivers"]}

THIS NOTE IS FOR THE {s["label"].upper()} SESSION, {s["hours"]}.
  What leads it: {s["leads"]}
  Handover: {s["handover"]}
  How it usually behaves: {s["character"]}

Write about THAT session. Conditions from the other two are context for it, \
never the subject — say what they hand over, then say what it means for the \
one being traded.

THE SAME RULE BINDS THE INSTRUMENT, and more strictly. Every field you \
return - bias, headline, summary, levels, evidence - is about \
{a["instruments"].upper()} and nothing else. The other books appear in the \
data under `other_books_context_only` and they are exactly that: cite them \
where they change the read on {a["label"]}, since a divergence is worth a \
sentence, and never issue a call on them. A note scoped to one book that \
hands back a view on another has answered a question nobody asked.

Write the note from the data you are given and nothing else. Every claim must \
rest on a figure that appears in that data, quoted in the evidence field. If \
the data does not support a view, say the bias is neutral and give a low \
conviction — a hedged guess presented confidently is worse than no note.

WORK THROUGH EVERY BLOCK OF THE DATA BEFORE YOU CONCLUDE. Notes written before \
this instruction cited the gamma levels and the session ranges and silently \
ignored sector rotation in three runs out of five — that was not a judgement \
that it did not matter, it was the block not being read. Each of these answers \
a different question, and the first four should appear somewhere in the note:

{must_read}

If a block genuinely says nothing today, leave it out rather than padding the \
note. What is not acceptable is not looking.

Read the gamma levels the way a dealer-flow trader does: positive gamma means \
hedging dampens moves and price tends to pin between the walls; negative gamma \
means hedging amplifies them and ranges extend. Spot's position relative to \
the gamma flip is the single most important structural fact on the page. If \
`expiry` says it is OpEx week, say what that does to the walls.

Be concrete and unhedged in the direction call. Do not use disclaimers, do not \
mention that you are an AI, and do not recommend position sizes or give \
financial advice — describe conditions and levels, which is what a desk note \
does."""


_FENCE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.S)


def extract_json(text: str) -> Any | None:
    """The first JSON object in a model's answer, however it wrapped it.

    THREE WRAPPINGS SEEN IN PRACTICE, all from models that claim structured
    output support. A reasoning model prefixes its working ("Let me look at the
    gamma structure first… {…}"); a chat-tuned one fences the block in
    ```json; a third adds a sentence of preamble. Refusing all three and
    calling it a schema failure threw away answers that were sitting right
    there — the JSON was correct, the envelope was not.

    Brace-matched rather than regexed, because the report contains nested
    objects and a non-greedy `\\{.*\\}` stops at the first inner brace.
    """
    if not text:
        return None
    for candidate in (text, *(m.group(1) for m in _FENCE.finditer(text))):
        candidate = candidate.strip()
        start = candidate.find("{")
        if start < 0:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    with contextlib.suppress(ValueError, TypeError):
                        return json.loads(candidate[start : i + 1])
                    break
    return None


def valid_report(obj: Any) -> bool:
    """Does this actually carry a note, whichever mode produced it?

    THE SCHEMA IS ONLY ENFORCED BY THE PROVIDER IN STRICT MODE, and the weaker
    modes below do not enforce anything at all — so the shape is checked here
    rather than assumed. Only the fields the panel dereferences without
    guarding: a report missing `risks` renders fine, one missing `bias` does
    not.
    """
    if not isinstance(obj, dict):
        return False
    required = ("bias", "conviction", "headline", "summary", "drivers",
                "invalidation", "session_expectation", "levels_to_watch")
    if any(k not in obj for k in required):
        return False
    if obj.get("bias") not in BIASES:
        return False
    return isinstance(obj.get("drivers"), list) and isinstance(
        obj.get("levels_to_watch"), list
    )


def loose_ask(messages: list[dict[str, str]]) -> dict[str, str]:
    """The user turn, with the schema spelled out for the no-schema pass.

    In `json_object` mode the provider guarantees valid JSON and NOTHING about
    its shape, so the shape has to be in the prompt. Written as an annotated
    skeleton rather than as the JSON Schema itself: the schema is 90 lines of
    `additionalProperties` and `minItems` that cost tokens and describe
    validation rather than intent, and a model reads an example better.
    """
    return {
        "role": "user",
        "content": (
            messages[-1]["content"]
            + "\n\nReturn ONLY a JSON object, no prose around it, exactly this shape:\n"
            + """{
  "bias": one of "bullish" | "leaning bullish" | "neutral" | "leaning bearish" | "bearish",
  "conviction": integer 1-5,
  "headline": "one line, under 100 characters",
  "summary": "two or three sentences",
  "drivers": [ { "point": "...", "evidence": "the figures from the data",
                 "direction": "bullish" | "bearish" | "neutral" } ],   // 3-6 of them
  "invalidation": [ { "condition": "...", "flips_to": "..." } ],       // 2-4
  "session_expectation": "how the session should behave: trend, chop, range, squeeze",
  "levels_to_watch": [ { "instrument": "NQ", "level": "29,500", "why": "..." } ],
  "risks": [ "..." ]
}"""
        ),
    }


def _post(
    payload: dict[str, Any], key: str, timeout: int = REQUEST_TIMEOUT_SEC
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            # OpenRouter asks for these two so a request can be attributed;
            # they are not secret and not required, but sending them is the
            # polite side of a free tier.
            "HTTP-Referer": "http://localhost:3100",
            "X-Title": "NewsTerminal",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def generate(
    snap: dict[str, Any],
    model: str | None = None,
    label: str = "manual",
    session: str = "auto",
    asset: str = "all",
) -> dict[str, Any]:
    """Build the digest, ask the model, store and return the report."""
    key = _key()
    now = datetime.now(UTC)
    et = now.astimezone(ET)
    model = model or DEFAULT_MODEL
    sess = resolve_session(snap.get("clock") or {}, session)
    book = resolve_asset(asset)

    base: dict[str, Any] = {
        "ok": False,
        "id": f"{et:%Y%m%d-%H%M%S}",
        "created_utc": now.isoformat(),
        "created_et": et.isoformat(),
        "et_label": et.strftime("%a %d %b, %H:%M ET"),
        "model": model,
        "label": label,
        "session": sess,
        "session_label": SESSIONS[sess]["label"],
        "asset": book,
        "asset_label": ASSETS[book]["label"],
        "report": None,
        "error": None,
        "digest": None,
        "usage": None,
    }

    if not key:
        base["error"] = (
            "No OPENROUTER_API_KEY. Add one to .env.local and restart the collector — "
            "the report is written by a model and there is deliberately no local "
            "fallback that would invent a bias."
        )
        return base

    digest = build_digest(snap, sess, book)
    base["digest"] = digest

    messages = [
        {"role": "system", "content": system_prompt(sess, book)},
        {
            "role": "user",
            "content": (
                f"Terminal snapshot at {digest.get('as_of_et')} "
                f"({digest.get('session_phase')}).\n\n"
                f"```json\n{json.dumps(digest, indent=1, default=str)}\n```\n\n"
                f"Write the note for the {SESSIONS[sess]['label']} session, "
                f"about {ASSETS[book]['instruments']}."
            ),
        },
    ]

    attempts: list[dict[str, Any]] = []
    # (model, mode) pairs, weakest-last.
    #
    # THE MODE HAS TO DEGRADE AS WELL AS THE MODEL, because "supports
    # structured_outputs" in OpenRouter's metadata describes the MODEL and the
    # request is served by a PROVIDER. On the first real run, dots-3-note's
    # provider rejected a strict schema outright with a 400 while advertising
    # support for it. `json_object` asks only for valid JSON, which nearly
    # every provider honours, and the schema is described in the prompt instead
    # — with `valid_report` checking the shape on the way back, since nothing
    # is enforcing it any more.
    plan: list[tuple[str, str]] = []
    for candidate in model_chain(model):
        plan.append((candidate, "schema"))
    for candidate in model_chain(model):
        plan.append((candidate, "json"))
    # Each pair gets more than one shot, because the failures are intermittent.
    plan = [pair for pair in plan for _ in range(TRIES_PER_PAIR)]

    started = time.monotonic()
    for candidate, mode in plan:
        if len(attempts) >= MAX_ATTEMPTS:
            break
        # RESERVE ROOM FOR THE ATTEMPT, do not merely check the budget is
        # unspent.
        #
        # This was `elapsed > BUDGET_SEC`, which bounds when an attempt may
        # START and says nothing about when the endpoint RETURNS: a request
        # beginning at 209s with the budget at 210 is allowed, and the caller
        # then waits for however long that request takes. Measured on a
        # saturated free pool: two attempts, 301 seconds, and a `curl -m 280`
        # gave up before the answer arrived.
        #
        # AND THE PER-REQUEST TIMEOUT IS NOT A CEILING EITHER. `urlopen`'s
        # `timeout` is per socket operation, not per request — every chunk that
        # arrives resets it. A reasoning model that trickles bytes while it
        # deliberates never idles for 70 seconds, so REQUEST_TIMEOUT_SEC = 70
        # sat there while single attempts ran past 150s. That is why the
        # reservation below is `_ATTEMPT_RESERVE` rather than
        # REQUEST_TIMEOUT_SEC: the reserve is what an attempt actually costs,
        # observed, not what the socket option claims to bound it at.
        elapsed = time.monotonic() - started
        if elapsed + _ATTEMPT_RESERVE > BUDGET_SEC:
            attempts.append({
                "model": candidate, "mode": mode,
                "error": (
                    f"not attempted — {elapsed:.0f}s of the {BUDGET_SEC:.0f}s budget "
                    f"spent, too little left to finish one"
                ),
            })
            break
        payload: dict[str, Any] = {
            "model": candidate,
            "messages": messages if mode == "schema" else [*messages[:-1], loose_ask(messages)],
            # Low but not zero: the schema already constrains the shape, and a
            # touch of variation keeps the prose from reading like a template.
            "temperature": 0.3,
            # 6000, NOT 2000, BECAUSE REASONING IS COUNTED IN IT.
            #
            # `max_tokens` caps completion tokens and the thinking is completion
            # tokens too — a trivial "return this JSON" ask to Nemotron spent 39
            # of its 48 there. The report body is around 1,200 tokens, so a
            # 2,000 budget left almost nothing once a reasoning model had
            # deliberated, and a truncated answer arrives here as the useless
            # "no JSON object in the answer".
            #
            # It is NOT a provider ceiling: `budget_probe.py` got a 404 at 200
            # and a clean answer at 4,000 from the same endpoint minutes apart.
            # That flakiness is handled by RETRYABLE, not by this number.
            #
            # Raised again to 12,000 after watching real runs come back with
            # `finish_reason=length` at 6,000 — a reasoning model handed the
            # full digest deliberates for thousands of tokens before it writes
            # anything, and a truncated answer costs the whole attempt.
            "max_tokens": 12000,
            # Ask for a short think rather than none: these models reason by
            # default and excluding it outright degrades the answer, but the
            # note does not need three thousand tokens of deliberation.
            "reasoning": {"effort": "low"},
        }
        if mode == "schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "session_bias", "strict": True, "schema": SCHEMA},
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        try:
            doc = _post(payload, key)
        except urllib.error.HTTPError as e:
            # The body carries OpenRouter's actual complaint — a saturated
            # shared pool, an unknown model id, a schema the model cannot
            # honour — and the bare status code alone would send you looking in
            # the wrong place.
            detail = ""
            with contextlib.suppress(OSError):
                detail = e.read().decode("utf-8", errors="replace")[:400]
            err = f"HTTP {e.code}: {detail or e.reason}"
            attempts.append({"model": candidate, "mode": mode, "error": err})
            # A 400 on the strict schema is the provider refusing the
            # schema, not a bug in it — the loose pass exists for exactly
            # that, so keep going. Anything else non-retryable stops here.
            if e.code in RETRYABLE or (e.code == 400 and mode == "schema"):
                continue
            base["error"] = f"OpenRouter {err}"
            base["attempts"] = attempts
            return base
        except (urllib.error.URLError, OSError, ValueError) as e:
            attempts.append({"model": candidate, "mode": mode, "error": f"unreachable: {e}"})
            continue

        if doc.get("error"):
            msg = str(doc["error"].get("message", doc["error"]))
            attempts.append({"model": candidate, "mode": mode, "error": msg})
            if TRANSIENT_TEXT.search(msg):
                continue
            base["error"] = f"OpenRouter: {msg}"
            base["attempts"] = attempts
            return base

        try:
            choice = doc["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError):
            attempts.append({"model": candidate, "mode": mode,
                             "error": "unexpected response shape"})
            continue

        # `content` CAN BE NULL, AND IS, ON REASONING MODELS. Several of them
        # return an empty content with the whole answer in `reasoning`, and one
        # crashed the generator outright by reaching `content[:2000]` on a
        # None. Coerced to a string, with `reasoning` as the fallback source —
        # the JSON is often in there verbatim and `extract_json` will find it.
        content = msg.get("content") or msg.get("reasoning") or ""
        if not isinstance(content, str):
            content = str(content)
        if not content.strip():
            attempts.append({
                "model": candidate, "mode": mode,
                "error": f"empty answer (finish_reason={finish})",
            })
            continue

        report = extract_json(content)
        if report is None:
            # Not "it ignored the schema" — the JSON may be there and wrapped.
            # `extract_json` already tried the fences and the preamble, so
            # reaching here means there is no object in the answer at all.
            attempts.append({
                "model": candidate, "mode": mode,
                # `finish_reason=length` here means the budget ran out mid
                # answer, which is a different fix from a model that will not
                # produce JSON at all.
                "error": f"no JSON object in the answer (finish_reason={finish}, "
                         f"{len(content)} chars)",
            })
            base["raw"] = content[:2000]
            continue
        if not valid_report(report):
            missing = [k for k in ("bias", "conviction", "headline", "summary",
                                   "drivers", "invalidation", "session_expectation",
                                   "levels_to_watch") if k not in report]
            attempts.append({
                "model": candidate, "mode": mode,
                "error": f"JSON did not match the report shape (missing: {missing or 'bias enum'})",
            })
            base["raw"] = content[:2000]
            continue

        base["ok"] = True
        base["report"] = report
        base["mode"] = mode
        # THE MODEL THAT ANSWERED, not the one asked for. A note written by the
        # second choice has to say so — "which model wrote this" is half the
        # provenance, and the panel prints this field.
        base["model"] = candidate
        base["usage"] = doc.get("usage")
        base["attempts"] = attempts
        _store(base)
        return base

    # Everything in the chain refused.
    base["attempts"] = attempts
    first = attempts[0]["error"] if attempts else "no models attempted"
    tried = ", ".join(f"{a['model']} ({a.get('mode', '?')})" for a in attempts)
    spent = time.monotonic() - started
    base["error"] = (
        f"Every free model refused in {spent:.0f}s. Tried: {tried}. "
        f"First reason — {first}"
    )
    return base


# --------------------------------------------------------------------------
# Storage — reports are kept so the calls can be judged later.
# --------------------------------------------------------------------------


def _store(rep: dict[str, Any]) -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"{rep['id']}.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rep, f)
        os.replace(tmp, path)
    except OSError:
        return
    # Trim oldest beyond KEEP. A cache that cannot be pruned is a slower
    # history list, never a reason to lose the report just written.
    with contextlib.suppress(OSError):
        # `name`, not `f` — the file handle above is still bound to `f` at this
        # point and reusing it here is the same one-name-two-meanings shadow
        # that mypy caught in the source modules.
        files = sorted(n for n in os.listdir(REPORTS_DIR) if n.endswith(".json"))
        for name in files[:-KEEP]:
            os.remove(os.path.join(REPORTS_DIR, name))


def history(limit: int = 20) -> list[dict[str, Any]]:
    """Stored reports, newest first — id, time and the call, without the digest."""
    if not os.path.isdir(REPORTS_DIR):
        return []
    out: list[dict[str, Any]] = []
    try:
        files = sorted((f for f in os.listdir(REPORTS_DIR) if f.endswith(".json")), reverse=True)
    except OSError:
        return []
    for f in files[:limit]:
        try:
            with open(os.path.join(REPORTS_DIR, f), encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        r = d.get("report") or {}
        out.append({
            "id": d.get("id"),
            "et_label": d.get("et_label"),
            "created_et": d.get("created_et"),
            "label": d.get("label"),
            "model": d.get("model"),
            "session": d.get("session"),
            "session_label": d.get("session_label"),
            "asset": d.get("asset"),
            "asset_label": d.get("asset_label"),
            "bias": r.get("bias"),
            "conviction": r.get("conviction"),
            "headline": r.get("headline"),
        })
    return out


def load(report_id: str) -> dict[str, Any] | None:
    path = os.path.join(REPORTS_DIR, f"{os.path.basename(report_id)}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            result: dict[str, Any] = json.load(fh)
            return result
    except (OSError, ValueError):
        return None


def latest() -> dict[str, Any] | None:
    h = history(1)
    return load(h[0]["id"]) if h and h[0].get("id") else None


def configured() -> dict[str, Any]:
    """What the panel needs to explain itself when there is no key."""
    return {"enabled": bool(_key()), "model": DEFAULT_MODEL}
