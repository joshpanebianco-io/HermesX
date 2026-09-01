import type { Terminal } from "@/types/terminal";

/**
 * The shape the UI renders when there is nothing behind the collector.
 *
 * ONE DEFINITION, TWO CALLERS. The server component and the route handler both
 * need an empty `Terminal` when the collector cannot be reached, and both had
 * their own literal — so adding `ranges`, `earnings` and `expiry` broke the
 * build in two files at once and would have broken it in two files every time
 * after that. A shared builder makes "what an empty terminal looks like" a
 * single fact.
 *
 * EVERY BLOCK IS EMPTY, NOT ABSENT, and nothing is invented. A panel handed an
 * empty array renders its own "nothing here, and here is why" state; a panel
 * handed a plausible-looking fabricated one cannot.
 */
export function offlineTerminal(reason: string, api: string): Terminal {
  const now = new Date().toISOString();
  return {
    ok: false,
    built_utc: now,
    started_utc: now,
    // The clock is the one block with no sensible empty value — it is
    // arithmetic on the wall clock rather than data, and every consumer already
    // guards on it because the collector may not have answered yet.
    clock: undefined as never,
    status: {},
    age_min: {},
    quotes: [],
    sectors: [],
    wire: [],
    calendar: [],
    earnings: [],
    rates: { curve: [], real: [], spreads: [], policy: {}, strip: [], path: {}, as_of: null },
    ranges: { assets: {} },
    constituents: { indices: {} },
    fed: [],
    policy_meetings: { meetings: [], anchor: null, anchor_src: null },
    volterm: {
      points: [],
      ratio: null,
      ratio_label: "VIX/VIX3M",
      shape: "unknown",
      note: null,
      skew: null,
      skew_pct: null,
    },
    gex: { assets: {}, enabled: false, book: "front" },
    expiry: {
      today: now.slice(0, 10),
      opex_week: false,
      monthly_expiry: "",
      days_to_opex: null,
      next: [],
      note: null,
    },
    offline: { reason, api },
  };
}

/** The reason an upstream call failed, in words a panel can print. */
export function failureReason(e: unknown): string {
  if (e instanceof Error) {
    return e.name === "TimeoutError" ? "the collector did not answer in time" : e.message;
  }
  return "unknown error";
}
