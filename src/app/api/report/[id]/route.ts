import { NextResponse } from "next/server";
import type { ReportFeed } from "@/types/terminal";

/**
 * One stored report by id, so a past call can be reopened.
 *
 * The id is a timestamp slug the collector minted (`20260831-090500`) and it
 * goes into a path on the collector, so it is validated rather than trusted:
 * the panel is the only thing that produces these, but a route handler that
 * pastes a client string into an upstream URL has to say why it is safe.
 */

export const dynamic = "force-dynamic";
export const revalidate = 0;

const API = process.env.NT_API ?? "http://127.0.0.1:8100";
const ID = /^[0-9]{8}-[0-9]{6}$/;

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  if (!ID.test(id)) {
    return NextResponse.json({
      config: { enabled: false, model: "" },
      latest: null,
      history: [],
      offline: { reason: `not a report id: ${id}`, api: API },
    } satisfies ReportFeed);
  }
  try {
    const r = await fetch(`${API.replace(/\/$/, "")}/api/report/${id}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!r.ok) throw new Error(`collector returned HTTP ${r.status}`);
    return NextResponse.json((await r.json()) as ReportFeed);
  } catch (e) {
    return NextResponse.json({
      config: { enabled: false, model: "" },
      latest: null,
      history: [],
      offline: {
        reason: e instanceof Error ? e.message : "unknown error",
        api: API,
      },
    } satisfies ReportFeed);
  }
}
