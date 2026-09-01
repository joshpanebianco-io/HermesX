import { NextResponse } from "next/server";
import type { Terminal } from "@/types/terminal";
import { failureReason, offlineTerminal } from "@/lib/offline";

/**
 * The browser's only door to the collector.
 *
 * WHY A PROXY AND NOT A DIRECT FETCH. The collector's address is server-side
 * configuration (`NT_API`, deliberately not `NEXT_PUBLIC_`), and a client that
 * fetched it directly would have to be told where it lives — which puts the
 * shape of the machine's private network into a JavaScript bundle for no gain.
 * It also means CORS never enters into it and the polling client has exactly
 * one URL to know.
 *
 * IT ALWAYS RETURNS 200 WITH A BODY. A collector that is down is a NORMAL
 * state — it is a separate process the reader can close — and modelling it as
 * an HTTP error would make every panel's error path a network error path. The
 * `offline` block says what happened and the UI renders the reason across the
 * chassis rather than an empty screen.
 */

export const dynamic = "force-dynamic";
export const revalidate = 0;

const API = process.env.NT_API ?? "http://127.0.0.1:8100";

export async function GET() {
  try {
    const r = await fetch(`${API.replace(/\/$/, "")}/api/terminal`, {
      cache: "no-store",
      // Generous but finite: the collector answers from memory in under a
      // millisecond, so anything approaching this means it is wedged rather
      // than busy, and a hung proxy is worse than a stated failure.
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) {
      return NextResponse.json(
        offlineTerminal(`collector returned HTTP ${r.status}`, API),
      );
    }
    const data = (await r.json()) as Terminal;
    return NextResponse.json(data, {
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  } catch (e) {
    return NextResponse.json(offlineTerminal(failureReason(e), API));
  }
}
