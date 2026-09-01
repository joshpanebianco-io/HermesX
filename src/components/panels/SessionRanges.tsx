"use client";

import type { ExpiryState, SessionRange } from "@/types/terminal";
import { Module } from "@/components/ui/Module";
import { Tick } from "@/components/ui/Tick";
import { num, pct } from "@/lib/format";
import { cn } from "@/lib/cn";
import { oneOf, usePersisted } from "@/lib/usePersisted";

/**
 * What each session actually traded.
 *
 * THE PANEL THAT WAS MISSING. A day high and low says the range was 240 points
 * and nothing about who set it — and this desk trades Asia, London and New York,
 * so "which session" is not a detail, it is the question. "London has already
 * taken out the Asia high and failed there" and "Asia set the high at 20:00 and
 * we have bled since" are the same two numbers and opposite setups.
 *
 * EACH BAR IS DRAWN ON ITS OWN SCALE, not a shared one. Asia routinely ranges
 * three times what pre-NY does; on a common axis the pre-NY bar would be a
 * sliver and its position — the thing worth reading — would be unreadable. The
 * range in points is printed beside each bar, which is where the comparison
 * between sessions belongs.
 *
 * THE MARKER IS CURRENT PRICE. Outside a session's own bar it clamps to the end
 * and the row says so, because "we are above everything Asia did" is the most
 * useful state this panel has and a marker pinned silently at the edge would
 * hide it.
 */

const ASSETS = ["NQ", "ES", "GC"];

export function SessionRanges({
  assets,
  expiry,
  ageMin,
  error,
}: {
  assets: Record<string, { last: number | null; sessions: SessionRange[] }>;
  expiry?: ExpiryState;
  ageMin?: number | null;
  error?: string | null;
}) {
  const keys = ASSETS.filter((k) => assets[k]);
  const [sel, setSel] = usePersisted<string>("ranges.asset", "NQ", oneOf("NQ", "ES", "GC"));
  const active = assets[sel] ?? assets[keys[0]];

  return (
    <Module
      title="Session ranges"
      sub={expiry?.opex_week ? "OpEx week" : undefined}
      ageMin={ageMin}
      error={error}
      bodyClassName="px-0 py-0"
      right={
        keys.length > 1 && (
          <div className="flex gap-0.5">
            {keys.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setSel(k)}
                className={cn(
                  "fig hit rounded px-1.5 py-px text-[10px]",
                  k === sel ? "bg-ink/10 text-ink" : "text-ink-4 hover:text-ink-2",
                )}
              >
                {k}
              </button>
            ))}
          </div>
        )
      }
    >
      {!active ? (
        <p className="px-3 py-5 text-center text-[11px] text-ink-4">
          No session data yet — the collector segments the last two days of bars.
        </p>
      ) : (
        <>
          <ul className="py-1">
            {active.sessions.map((s) => (
              <Row key={s.key} s={s} last={active.last} />
            ))}
          </ul>
          {expiry && <ExpiryLine e={expiry} />}
        </>
      )}
    </Module>
  );
}

function Row({ s, last }: { s: SessionRange; last: number | null }) {
  if (!s.ok) {
    return (
      <li className="flex items-center gap-2 px-3 py-[3px] opacity-45">
        <span className="fig w-[52px] shrink-0 text-[10.5px] text-ink-4">{s.label}</span>
        <span className="flex-1 text-[10px] text-ink-4">not traded yet</span>
      </li>
    );
  }

  const pos = s.pos;
  // Clamped for drawing, but the row says which end it is pinned to rather than
  // letting the marker sit silently at the edge.
  const clamped = pos === null ? null : Math.max(0, Math.min(1, pos));
  const beyond = pos === null ? null : pos > 1 ? "above" : pos < 0 ? "below" : null;

  return (
    <li className="flex items-center gap-2 px-3 py-[3px]">
      <span className="fig w-[52px] shrink-0 text-[10.5px] text-ink-2">{s.label}</span>
      <Tick
        value={num(s.low, 0)}
        className="fig w-[58px] shrink-0 text-right text-[10px] text-ink-4"
      />
      <span
        className="relative h-[9px] flex-1 rounded-sm bg-ring/60"
        title={`${s.label} ${num(s.low)}–${num(s.high)} · range ${num(s.range, 1)} · ${
          s.start_et ?? ""}–${s.end_et ?? ""} ET`}
      >
        {clamped !== null && (
          <span
            className="absolute top-1/2 h-[13px] w-[2px] -translate-y-1/2 rounded-full"
            style={{
              left: `calc(${clamped * 100}% - 1px)`,
              background: beyond ? "var(--flip)" : "var(--spot)",
            }}
          />
        )}
      </span>
      <Tick value={num(s.high, 0)} className="fig w-[58px] shrink-0 text-[10px] text-ink-4" />
      <span
        className={cn(
          "fig w-[52px] shrink-0 text-right text-[10px]",
          beyond ? "text-flip" : (s.chg_pct ?? 0) >= 0 ? "up" : "down",
        )}
        title={
          beyond === "above"
            ? `Price is above everything ${s.label} traded`
            : beyond === "below"
              ? `Price is below everything ${s.label} traded`
              : "Change across that session"
        }
      >
        <Tick
          value={beyond === "above" ? "↑ out" : beyond === "below" ? "↓ out" : pct(s.chg_pct)}
        />
      </span>
      <span className="fig hidden w-[46px] shrink-0 text-right text-[10px] text-ink-4 sm:block">
        {num(s.range, 0)}
      </span>
      {last === null && <span className="sr-only">no current price</span>}
    </li>
  );
}

/**
 * The expiry line. One sentence, and only when it says something.
 *
 * It matters more here than on an ordinary terminal because the walls this
 * app borrows are open-interest structures with a maturity: in OpEx week the
 * near book is at its largest and price pins to it, and the Monday after, the
 * same strikes carry almost nothing.
 */
function ExpiryLine({ e }: { e: ExpiryState }) {
  const next = e.next?.[0];
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 border-t border-ring/40 px-3 py-1.5 text-[10px]">
      {e.opex_week ? (
        <span className="fig rounded bg-flip/20 px-1.5 py-px text-[9px] text-flip">OPEX WEEK</span>
      ) : (
        <span className="eyebrow text-[9px]">Next</span>
      )}
      {next && (
        <>
          <span className="text-ink-2">{next.label}</span>
          <span className="fig text-ink-4">
            {next.days === 0 ? "today" : `in ${next.days}d`}
          </span>
        </>
      )}
      {e.opex_week && <span className="text-ink-3">{e.note}</span>}
    </div>
  );
}
