# HERMESX

Named for Hermes — god of messages, information and speed, which is the whole
job description. A single-desk market terminal: the wire, the board, the curve,
sector rotation, the economic calendar and borrowed gamma levels, on one
session clock.

(The folder and the Python package are still `NewsTerminal`/`newsterminal` —
the brand renamed on 2026-09-01, the plumbing deliberately did not.)

The mark is the owner's own winged-helm line art, traced to a single vector
path (`src/lib/hermesMark.ts`) and recoloured to the terminal's chrome hues.

Next.js 15 front end on **:3100**, a Python collector on **:8100**. Sister
project to GEXYGEN, which owns :3000/:8000 — the two are meant to run at the
same time, and this one reads GEXYGEN's gamma levels.

```powershell
npm install
.\dev.ps1              # both halves, each in its own window
.\server\run.ps1       # or just the collector — http://127.0.0.1:8100
npm run dev            # or just the web — http://localhost:3100
```

```bash
npm run typecheck      # tsc
npm run lint           # eslint
npm run py:lint        # ruff
npm run py:types       # mypy
npm run py:test        # pytest — the wire classifiers
npm run check          # all five
```

Three tabs: **Terminal**, **Report**, **Settings** — `?tab=report` deep-links.

---

## ⚠ Personal use only — this is NOT fit to ship

GEXYGEN is constrained to public-domain and openly-licensed sources because it
is going commercial. **This project deliberately is not.** It is a single
instrument on one desk for one reader, and it uses two classes of source that
are fine for that and for nothing else:

| Source | What is permitted | What is not |
|---|---|---|
| **Yahoo Finance** quotes and intraday bars | personal, non-commercial use | redistribution, or serving them to any other user |
| **Publisher RSS** — Reuters, AP, Bloomberg, WSJ, FT, NYT, BBC, Guardian, Al Jazeera, CNBC, MarketWatch, Investing.com | reading headlines and summaries yourself | republication, or putting them in front of a third party |

If any of this is ever shown to another person or a paying one, the quote feed
and the wire both have to be re-sourced first. Nothing else in the codebase
changes — the collector's source modules are independent by design, so swapping
`quotes.py` and `wire.py` is the whole job.

The Treasury curve, the NY Fed reference rates and the Federal Reserve feeds are
US Government works and carry no such restriction.

---

## What is on the screen

**Across the top — the alert line.** High-impact headlines only, typically a
handful out of four hundred, visible on every tab. It is not a second copy of
the wire: the wire column is gone on the other tabs and its newest item is gone
the moment you scroll, and this is what carries the four or five things an hour
that genuinely interrupt. It disappears entirely when there is nothing.

**Left column — the context a headline is read against**

- **Sessions.** Sydney, Tokyo, Hong Kong, Shanghai, London, Frankfurt, New York:
  who is open, local time, and how long until each changes. The London/New York
  overlap (08:00–11:30 ET) is called out separately because it is where the
  day's range is usually set. Plus the next recurring session moment — the data
  window, the open, FOMC hour, the close, CME settlement.
- **Session ranges.** What Asia, London, pre-NY and New York each actually
  traded — high, low, range and where price sits inside each — for NQ, ES and
  GC. The gap this filled: a day high/low says the range was 240 points and
  nothing about who set it, and "London has already taken out the Asia high and
  failed there" and "Asia set the high at 20:00 and we have bled since" are the
  same two numbers and opposite setups. Each bar is on its own scale because
  Asia routinely ranges three times what pre-NY does. Carries the OpEx line.
- **Gamma levels.** Three call walls, three put walls, the gamma flip, per asset
  (NQ, ES, GC), drawn as a price-ordered ladder with spot spliced into it.
  Borrowed from GEXYGEN, never recomputed — see below.
- **Rates & policy.** EFFR and SOFR from the NY Fed, the Treasury par curve with
  daily changes in basis points, 2s10s / 3m10y / 5s30s, the 10-year breakeven,
  and the **fed funds futures strip** — the market's expected policy rate month
  by month, and the tightening or easing priced between the near and far ends.

**Middle column — the wire**

~28 feeds merged newest-first, deduplicated across publishers, filterable two
ways at once: by **desk** (Markets, Macro, Policy, Geopolitics, Energy) and by
**impact** (High / Med / Low). Every item names its publisher and links back.

Impact is three exclusive tiers, not a threshold — "High" means *only* high, so
switching to it leaves you with a handful of lines rather than most of the tape.
**High is a thing that happened**: a released number, a decided rate move, a
strike that landed. Speculation about the same thing is demoted to Medium, which
is what separates "Fed cuts rates" from "Fed rate cut expectations build" —
they share every keyword and are not the same headline. On a live tape that
split is typically 4 high, 70 medium, 245 low.

Reuters and AP no longer publish a usable public feed, so both are recovered
through Google News' index with a `site:` query; the outlet that actually filed
the story is lifted out of the title suffix and used as the attribution.

**Right column — prices**

- **The book.** NQ/QQQ, ES/SPY, GC/GLD, plus YM and RTY.
- **Calendar.** Yesterday through the next three sessions, with day rules so a
  list that crosses midnight still reads as sorted. Actual, consensus and
  previous on one line, with a meaningful miss picked out in amber. **Colour is
  magnitude, never direction** — a hot CPI and a hot payrolls print are both
  "above consensus" and they mean opposite things.

  Three filters. **Mine** (on by default) narrows ~220 raw rows to the ~20 that
  reach NQ, ES and GC — judged on *theme and weight*, not country, so a Chinese
  GDP miss survives and a US housing-starts print does not. **US / EU / UK /
  APAC / Other** groups by the desk that trades it rather than the continent it
  is in: Australia and New Zealand sit under APAC because an RBA decision prints
  inside the Asia session. **High / Med / Low** uses the same vocabulary as the
  wire. Every row also shows which trading session it prints into.
- **Earnings.** Large caps only — the collector drops anything under $50bn that
  is not a bellwether, so it is five or ten names a day rather than three
  hundred. AMC/BMO leads each row, because an after-hours report is tomorrow's
  gap and a pre-market one is this morning's.
- **Sector rotation.** The eleven SPDRs ranked by relative strength against SPY,
  defaulting to **1D** with 1W and 1M one click away, plus a breadth read from
  RSP vs SPY. The span is a real tension: rotation is properly a claim about
  weeks, but this terminal is read at the open to judge the day ahead.
- **Macro board.** Volatility (VIX, VVIX, MOVE, VXN), energy (WTI, Brent, nat
  gas, RBOB, heating oil), rates futures, FX (DXY and five crosses), metals and
  ags, global indices, and risk appetite (BTC, ETH, HYG, TLT).

Every row carries a sparkline drawn against the **prior close**, not the series
low — so a line that spent the session under water sits visibly under the rule.

---

## The Report tab — session bias

A model reads the whole terminal and calls a bias: **bullish → bearish** on a
five-point scale with a conviction of 1–5, the drivers with the figures behind
each, how the session is expected to behave, the levels to watch, what would
invalidate the call, and the risks.

**It is written for a named session.** This desk trades Asia and London as well
as New York, and a note written for the New York open is the wrong note at 20:00
ET when Tokyo is about to go — what leads is different, the handover is
different, and "overnight" refers to the opposite thing. So the session is a
control on the panel: **Auto** resolves it from the ET clock, and Asia / London
/ NY are explicit. The choice reaches the model as a different system prompt
naming what leads that session, what hands over to it and how it usually
behaves, not as a filter on the data.

**The model forms the view** (owner's decision, 2026-08-31). The alternative was
a scored rules engine deciding the bias deterministically with the model only
narrating it. The trade was stated and accepted: two runs on identical data can
disagree, and there is no arithmetic to audit when a call is wrong.

Four things make it checkable anyway:

- It is handed a **curated digest**, not the raw snapshot — ~2 kB of the figures
  a desk would actually read, decided in `build_digest` where it can be
  reviewed, rather than 250 KB of strike maps and 300 headlines.
- Every report is **stamped** with the model, the moment, and the exact digest
  it saw. "Show the data it saw" is a button on the report.
- The output is a **structured object**, so the panel renders fields instead of
  regexing prose, and the model has to commit to a direction rather than hedge.
- Reports are **kept** (40 of them). The 09:00 call is still there at 15:00,
  which is the only way to learn whether the calls are any good.

**No key, no report.** There is deliberately no local fallback that invents a
bias — one rendered in the same frame as a real one would be indistinguishable
from it. Add a free `OPENROUTER_API_KEY` and restart the collector; the panel
tells you exactly that until you do.

### The free tier is flaky, and the chain is why

A `:free` model does not get its own capacity — it routes to a provider pool
shared with every other OpenRouter user. Measured on this desk in one sitting:

- `z-ai/glm-5.2:free` returned **429, four times in a row** — pool saturated.
  Not our quota; retrying does not clear it.
- `nvidia/nemotron-3-super-120b-a12b:free` returned **404 at `max_tokens` 200
  and a clean answer at 4,000**, minutes apart, for otherwise identical
  requests. It is not a route that is missing and not a budget ceiling; the
  endpoint simply falls over. `server/tools/budget_probe.py` is what measured
  that.
- `dots-studio/dots-3-note-preview:free` **rejected a strict JSON schema with a
  400** while advertising `structured_outputs` support — because the metadata
  describes the *model* and the request is served by a *provider*.

So the request degrades along two axes rather than one. **Model:** the
configured model first, then the others in `FALLBACK_MODELS`. **Mode:** strict
`json_schema` first, then `json_object` with the shape described in the prompt
and validated on the way back by `valid_report`, since nothing is enforcing it
any more. Each pair gets two tries, capped at ten attempts total.

Three more things that came out of the first real runs:

- **`max_tokens` is 12,000, not 2,000.** Reasoning tokens are completion
  tokens, and a reasoning model handed the full digest deliberates for
  thousands before writing anything — a 2,000 budget returned
  `finish_reason=length` and an empty `content`.
- **The JSON is extracted, not just parsed.** Models fence it in ```json,
  prefix their working, or return `content: null` with the answer in
  `reasoning`. All three were thrown away as "schema failures" when the JSON
  was sitting right there.
- **A report can take two to three minutes** end to end when the first pool is
  saturated. The route handler waits 290s; the panel says so while it works.

The finished report names **whichever model actually answered**, not the one
configured — that is half the provenance.

`?tab=report` deep-links straight into it.

---

## Settings — the palette

Twelve presets and seventeen hues, imported wholesale from GEXYGEN by
`server/tools/build_theme.py` rather than rebuilt. Each hue carries eight tiers
generated as fixed lightness and chroma targets in OKLCH and clamped into sRGB
per tier; every one was contrast-checked before it was written down, and no
offered hue lands within 30° of the flip's amber, so a themed wall can never be
mistaken for the flip line. No red-and-green pair is offered, deliberately — it
is the obvious trading palette and the one that fails for the ~8% of men with
deuteranopia or protanopia.

The theme is a cookie, applied to `<html>` on the server so the first paint is
already themed. **The five desk hues on the wire are deliberately not settable**:
they are identity tags that must stay distinguishable at equal value, and
letting a preset move them would let a headline rail collide with the up/down
palette — a green rail reading as "bullish" is the one confusion this palette
exists to prevent.

Retinting here changes what a wall looks like *in this browser only*.
NinjaTrader and the TradingView indicator read their own files, so what you are
trading away is the cross-surface promise. The Settings page says so.

---

## Where the gamma levels come from

They are read from GEXYGEN's compute service at `/api/levels.txt`, which already
publishes exactly the seven numbers this terminal wants and ranks the top three
walls the way GEXYGEN's own chart indicators do.

They are **not** recomputed here, deliberately. Two engines that both turn an
option chain into a call wall will disagree the moment either is touched, and
then there are two call walls on two screens and no way to know which is real.
The colours are GEXYGEN's canonical palette byte-for-byte, so a wall is the same
teal here, in GEXYGEN, on the TradingView indicator and in NinjaTrader.

If GEXYGEN is not running, the panel says so and shows nothing. It never falls
back to a remembered set — a wall from an hour ago drawn as though it were
current is the worst thing this kind of product can do.

Set `NT_GEXYGEN_API=` (empty) to disable the panel entirely.

---

## Architecture

```
NewsTerminal/
├─ dev.ps1                    both halves, each in its own window
├─ src/                       Next.js 15, App Router
│  ├─ app/
│  │  ├─ page.tsx             server-rendered first paint, real data
│  │  ├─ globals.css          design tokens — GEXYGEN's palette
│  │  ├─ api/terminal/        the browser's only door to the collector
│  │  └─ api/report/          GET the last note, POST a new one
│  ├─ components/
│  │  ├─ Terminal.tsx         the three-column shell, polls every 20s
│  │  ├─ panels/              Wire, Board, Gamma, Rates, Rotation, Calendar, Sessions, Report
│  │  ├─ shell/               Header (ticker strip), StatusRail
│  │  └─ ui/                  Module, Sparkline
│  └─ lib/format.ts           every number in the product formats here
└─ server/
   ├─ run.ps1                 the collector, with its live source feed
   ├─ tools/probe.py          hit every source once and print what came back
   └─ newsterminal/
      ├─ collector.py         one thread, per-source cadences, the tick log
      ├─ report.py            the digest, the schema, the OpenRouter call
      ├─ api.py               reads of the warm snapshot; no fetching on the request path
      ├─ http.py              fetch + disk cache; never raises
      ├─ sessions.py          the clock
      ├─ expiry.py            OpEx, triple witching, month and quarter end
      └─ sources/
         ├─ quotes.py         Yahoo spark — 47 instruments in 4 requests
         ├─ wire.py           ~28 RSS feeds, classified and deduplicated
         ├─ rates.py          Treasury CSV + NY Fed + fed funds strip
         ├─ calendar.py       Nasdaq economic events, region- and session-tagged
         ├─ earnings.py       Nasdaq earnings, large caps only
         ├─ ranges.py         Asia / London / pre-NY / NY high-low
         └─ gex.py            GEXYGEN levels.txt adapter
```

**The collector holds a warm snapshot; the API only reads it.** A page load
costs one in-memory read rather than forty upstream fetches, which is why the
first paint arrives complete instead of as a grid of skeletons.

**Cadences match each source's own clock** rather than one shared number:
quotes 20s, gamma 30s, wire 120s, sectors 5m, calendar 10m, rates 30m. Polling a
publisher's RSS faster than it regenerates is rude without being informative.

**Every panel states its own age.** Six panels on six clocks half an hour apart
means one "as of" in the corner of the page would be a lie about five of them.
The chip is silent grey when fresh, amber past ten minutes, red past an hour.

**Nothing is fabricated and nothing is silently stale.** A source that fails
leaves its previous data in place with the age climbing and the reason on the
module's face; a source that has never succeeded renders as an empty panel that
says why. The collector window shows one row per source per refresh with a `└─`
line under anything degraded.

---

## The collector window

```
TIME     SOURCE       ITEMS     AGE  SRC    STATUS
06:51:51 quotes          47    0.0m  live   ok
06:51:53 gex              3    0.0m  live   ok
06:51:54 wire           309    0.0m  live   ok
         └─ 27/28 feeds
06:51:56 sectors         13    0.0m  live   ok
06:51:57 calendar       221    0.0m  live   ok
06:51:58 rates           23    0.0m  live   ok
```

`SRC` is where the bytes came from: `live` off the network, `cache` from a fresh
cache entry, `stale` when the fetch failed and an old copy was served instead —
which is always labelled, never silent. `NT_TICK_LOG=0` silences the table.

`python server/tools/probe.py` hits every source once and prints the actual
rows, which is the right amount of detail when a publisher has changed a feed
URL and one line of tick log is not enough.

---

## Configuration

Everything has a working default; the terminal runs on an empty environment.
Copy `.env.example` to `.env.local` to change any of it. Optional free keys
(`FRED_API_KEY`, `EIA_API_KEY`) widen coverage and their absence is stated
rather than hidden.
