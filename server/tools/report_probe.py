"""Generate one report in-process and print the traceback if it fails.

The collector swallows nothing, but its traceback goes to its own window — this
runs the same call where the output is readable. Loads ../.env.local the way
run.ps1 does so the key is taken from the file rather than the shell, and never
prints it.

    python server/tools/report_probe.py [asia|london|ny|auto]
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
    key = os.environ.get("OPENROUTER_API_KEY", "")
    print(f"key present: {bool(key)}  (length {len(key)})")
    print("chain:", R.model_chain(R.DEFAULT_MODEL))

    snap = json.loads(
        urllib.request.urlopen("http://127.0.0.1:8100/api/terminal", timeout=60)
        .read()
        .decode("utf-8")
    )
    try:
        rep = R.generate(snap, session=want, label="probe")
    except Exception:  # noqa: BLE001 - a probe: any failure is the thing being looked at
        print("\nRAISED:")
        traceback.print_exc()
        return

    print(f"\nok={rep['ok']}  model={rep['model']}  session={rep.get('session_label')}")
    for a in rep.get("attempts") or []:
        print(f"  tried {a['model']}: {str(a['error'])[:110]}")
    if rep.get("error"):
        print("error:", rep["error"][:400])
    body = rep.get("report")
    if body:
        print(f"\n{body['bias'].upper()}  conviction {body['conviction']}/5")
        print(body["headline"])
        print()
        print(body["summary"])
        print("\nWHY")
        for d in body["drivers"]:
            print(f"  [{d['direction']:<8}] {d['point']}")
            print(f"             {d['evidence']}")
        print("\nSESSION")
        print(" ", body["session_expectation"])
        print("\nLEVELS")
        for lv in body["levels_to_watch"]:
            print(f"  {lv['instrument']:<6} {lv['level']:<16} {lv['why']}")
        print("\nWHAT WOULD CHANGE IT")
        for v in body["invalidation"]:
            print(f"  {v['condition']}  ->  {v['flips_to']}")
        print("\nRISKS")
        for x in body["risks"]:
            print(" ", x)


if __name__ == "__main__":
    main()
