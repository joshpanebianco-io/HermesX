"""Generate one report in-process and print the traceback if it fails.

The collector swallows nothing, but its traceback goes to its own window — this
runs the same call where the output is readable. Loads ../.env.local the way
run.ps1 does so the key is taken from the file rather than the shell, and never
prints it.

    python server/tools/report_probe.py [asia|london|ny|auto] [all|NQ|ES|GC]
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.request

# The report is full of typographic punctuation — en-dashes, non-breaking
# hyphens, curly quotes — and a Windows console is cp1252, which cannot encode
# any of it. Without this the probe crashes while PRINTING a report that
# generated perfectly, which reads like a failure and is not one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HERE)

ENV = os.path.join(os.path.dirname(HERE), ".env.local")
if os.path.exists(ENV):
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from newsterminal import report as R  # noqa: E402


def main() -> None:
    want = sys.argv[1] if len(sys.argv) > 1 else "auto"
    asset = sys.argv[2] if len(sys.argv) > 2 else "all"
    key = os.environ.get("OPENROUTER_API_KEY", "")
    print(f"key present: {bool(key)}  (length {len(key)})")
    print("chain:", R.model_chain(R.DEFAULT_MODEL))

    snap = json.loads(
        urllib.request.urlopen("http://127.0.0.1:8100/api/terminal", timeout=60)
        .read()
        .decode("utf-8")
    )
    try:
        rep = R.generate(snap, session=want, asset=asset, label="probe")
    except Exception:  # noqa: BLE001 - a probe: any failure is the thing being looked at
        print("\nRAISED:")
        traceback.print_exc()
        return

    print(f"\nok={rep['ok']}  model={rep['model']}  session={rep.get('session_label')}")
    for a in rep.get("attempts") or []:
        print(f"  tried {a['model']}: {str(a['error'])[:110]}")
    if rep.get("error"):
        print("error:", rep["error"][:400])
    facts = rep.get("facts") or {}
    print("\nPARTIAL:", facts.get("partial"))
    for lad in facts.get("ladders") or []:
        print(f"\nLADDER {lad['book']}  last {lad['last']}  em ±{lad['em']} ({lad['em_basis']})")
        for row in lad["rows"]:
            print(f"  {row['price']:>10}  {row['label']:<22} {row['dist'] if row['dist'] is not None else ''}")

    body = rep.get("report")
    if body:
        print("\n" + body["thesis"])
        for c in body["calls"]:
            print(f"\n{c['book']}: {c['open_bias'].upper()} {c['conviction']}/5 · rest of day: "
                  f"{c['rest_of_day']} · wrong if: {c['wrong_if']}")
        for r in body["reads"]:
            print(f"\n== {r['book']} · {r['regime']}")
            print("  " + "  ->  ".join(r["chain"]))
            print("  OPEN  ", r["at_open"])
            print("  WRONG ", r["wrong_if"])
            print("  LATER ", r["rest_of_day"])
            for x in r["flips"]:
                print("  FLIPS ", x)
            for d in r["drivers"]:
                print(f"  [{d['tone']:<7}] {d['label']}: {d['text']}")
        print("\nGAMMA     ", body["gamma_read"])
        print("ROTATION  ", body["rotation_read"])
        for n in body["catalyst_notes"]:
            print(f"  catalyst {n['id']}: {n['note']}")
        for h in body["headlines"]:
            print(f"  headline {h['id']} {h['books']}: {h['note']}")
        print("CROSS     ", body["cross_asset"])
        for x in body["risks"]:
            print("  risk:", x)


if __name__ == "__main__":
    main()
