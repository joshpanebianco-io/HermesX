import { NextResponse } from "next/server";
import type { ReportFeed } from "@/types/terminal";

/**
 * The report proxy — GET reads the last one, POST writes a new one.
 *
 * SAME REASONING AS /api/terminal: the collector's address is server-side
 * configuration and the browser has no business knowing it. What is different
 * here is the timeout. Generating a report means a round trip to a model that
 * is thinking, and on a free tier that can take most of a minute — so this one
 * waits far longer than the terminal poll, and the panel shows a working state
 * rather than a spinner with no explanation.
 */

export const dynamic = "force-dynamic";
export const revalidate = 0;
// FIVE MINUTES, MEASURED RATHER THAN GUESSED. A first real run took 188
// seconds: the free pool for the preferred model was saturated, so the chain
// walked to the next one, and a free reasoning endpoint handed the full digest
// is simply slow. 120s cut off a report that was about to arrive, which is the
// worst of both — the tokens were spent and the answer was thrown away.
export const maxDuration = 300;

const API = process.env.NT_API ?? "http://127.0.0.1:8100";

function offline(reason: string): ReportFeed {
  return {
    config: { enabled: false, model: "" },
    latest: null,
    history: [],
    offline: { reason, api: API },
  };
}

async function call(method: "GET" | "POST", timeoutMs: number) {
  const r = await fetch(`${API.replace(/\/$/, "")}/api/report`, {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!r.ok) throw new Error(`collector returned HTTP ${r.status}`);
  return (await r.json()) as ReportFeed;
}

function reason(e: unknown): string {
  if (e instanceof Error) {
    return e.name === "TimeoutError" ? "the collector did not answer in time" : e.message;
  }
  return "unknown error";
}

export async function GET() {
  try {
    return NextResponse.json(await call("GET", 10_000));
  } catch (e) {
    return NextResponse.json(offline(reason(e)));
  }
}

export async function POST() {
  try {
    return NextResponse.json(await call("POST", 290_000));
  } catch (e) {
    return NextResponse.json(offline(reason(e)));
  }
}
