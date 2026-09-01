"""Hit every source once and print what came back. `python tools/probe.py`.

Exists because the collector logs one line per source and that is the right
amount of noise for a running window and the wrong amount when a source has
just been written or a publisher has changed a feed URL. This prints the
actual rows.
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

from newsterminal.sessions import session_state
from newsterminal.sources import calendar as cal
from newsterminal.sources import gex, quotes, rates, wire


def rule(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def main() -> None:
    t0 = time.time()

    rule("CLOCK")
    c = session_state()
    print(f"{c['et_time']} ET  {c['et_date']}  |  {c['phase']['label']} — {c['phase']['note']}")
    print(f"open: {c['open_count']}  overlap: {c['overlap']}  weekend: {c['weekend']}")
    for s in c["sessions"]:
        state = "OPEN  " if s["open"] else "closed"
        print(f"  {s['label']:<11} {state} local {s['local_time']}  {s['next']} in {s['next_min']:>5}m")
    for m in c["markers"]:
        print(f"  next: {m['label']:<22} {m['et']} ET  in {m['in_min']:>4}m")

    rule("QUOTES")
    rows, st = quotes.collect()
    print(f"{st.items} rows | {st.source} | err={st.error} | {st.notes}")
    for r in rows:
        pct = f"{r['pct']:+.2f}%" if r["pct"] is not None else "   n/a"
        rp = f"{r['range_pos']:.2f}" if r["range_pos"] is not None else " -- "
        print(f"  {r['group']:<8} {r['key']:<8} {r['last']!s:>12}  {pct:>9}  rng={rp}  spark={len(r['spark']):>3}")

    rule("SECTORS")
    srows, sst = quotes.collect_sectors()
    print(f"{sst.items} rows | {sst.source} | err={sst.error}")
    for r in sorted(srows, key=lambda x: -(x.get("rs_month") or -99)):
        rsm = f"{r['rs_month']:+.2f}" if r.get("rs_month") is not None else "  n/a"
        d = f"{r['day_pct']:+.2f}%" if r.get("day_pct") is not None else "  n/a"
        print(f"  {r['key']:<6} {r['label']:<22} day={d:>8}  RS(1m)={rsm:>7}")

    rule("RATES")
    rt, rst = rates.collect()
    print(f"{rst.items} items | {rst.source} | err={rst.error} | {rst.notes}")
    print("  curve  :", ", ".join(f"{x['key']}={x['value']}({x['chg_bp']:+}bp)" for x in rt["curve"]))
    print("  spreads:", ", ".join(f"{x['label']}={x['value']}{x['unit']}" for x in rt["spreads"]))
    print("  policy :", rt["policy"])
    print("  path   :", rt["path"])
    print("  strip  :", ", ".join(f"{x['label']}={x['implied']:.3f}" for x in rt["strip"][:8]))

    rule("GEX  (needs GEXYGEN on :8000)")
    g, gst = gex.collect()
    print(f"{gst.items} assets | {gst.source} | err={gst.error} | {gst.notes}")
    for a, v in (g.get("assets") or {}).items():
        if not v.get("ok"):
            print(f"  {a}: DOWN — {v.get('error')}")
            continue
        print(f"  {a}: spot={v['spot']} regime={v['regime']} book={v['book']}")
        for lv in v["levels"]:
            print(f"      {lv['label']:<13} {lv['price']:>10}  {lv['dist']:+9.1f}  ({lv['dist_pct']:+.2f}%)")

    rule("CALENDAR")
    crows, cst = cal.collect()
    print(f"{cst.items} rows | {cst.source} | err={cst.error} | {cst.notes}")
    for r in [x for x in crows if x["score"] >= 3][:18]:
        a = r["actual_raw"] or "—"
        k = r["consensus_raw"] or "—"
        p = r["previous_raw"] or "—"
        print(f"  [{r['score']}] {r['date']} {r['et'] or '  :  '} {r['country'][:14]:<14} {r['event'][:40]:<40} A={a:>8} C={k:>8} P={p:>8}")

    rule("WIRE")
    items, feeds = wire.collect()
    ok = [f for f in feeds if f.ok]
    print(f"{len(items)} items from {len(ok)}/{len(feeds)} feeds")
    for f in feeds:
        if not f.ok:
            print(f"  DOWN  {f.name:<28} {f.error}")
    cats: dict[str, int] = {}
    for i in items:
        cats[i["category"]] = cats.get(i["category"], 0) + 1
    print("  by category:", cats)
    print("  hot:", sum(1 for i in items if i["hot"]))
    for i in items[:20]:
        t = (i["utc"] or "")[11:16]
        also = f"  (+{len(i['also'])})" if i.get("also") else ""
        print(f"  {t:>5} [{i['category'][:6]:<6}] {i['publisher'][:12]:<12} {i['title'][:78]}{also}")

    print(f"\nprobe finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
