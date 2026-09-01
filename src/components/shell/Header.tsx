"use client";

import type { Clock, Quote } from "@/types/terminal";
import { dir, num, pct } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Tick } from "@/components/ui/Tick";

type Tab = "terminal" | "report" | "settings";

/**
 * The header rail — identity on the left, state on the right.
 *
 * THE TICKER STRIP IS NOT A CRAWL. It is a fixed row of the instruments this
 * desk actually trades, always in the same order and always in the same place.
 * A scrolling strip is the thing every finance site does and it is wrong for
 * an instrument: you cannot glance at a moving target, and the whole value of
 * a header row is that NQ is always in the same six centimetres of glass.
 */
const TABS = [
  { key: "terminal" as const, label: "Terminal" },
  { key: "report" as const, label: "Report" },
  { key: "settings" as const, label: "Settings" },
];

export function Header({
  clock,
  quotes,
  live,
  onRefresh,
  tab,
  onTab,
}: {
  clock: Clock | null;
  quotes: Quote[];
  live: boolean;
  onRefresh: () => void;
  tab: Tab;
  onTab: (t: Tab) => void;
}) {
  // The strip's instruments, in trading order rather than payload order.
  const strip = ["NQ", "ES", "GC", "VIX", "US10Y", "DXY", "WTI", "BTC"]
    .map((k) => quotes.find((q) => q.key === k))
    .filter((q): q is Quote => Boolean(q));

  return (
    <header className="flex flex-col gap-0 border-b border-ring">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
        <div className="flex items-center gap-2">
          <Mark />
          <span className="wordmark fig text-[14px] font-semibold tracking-[0.14em]">
            HERMESX
          </span>
        </div>

        {/*
         * THE TABS SIT BESIDE THE WORDMARK, NOT ABOVE THE PANELS. The
         * instrument, the note written off it, and the controls for both — all
         * chrome-level views of one session, so they belong in the chassis
         * beside the clock and the state light rather than in a bar that would
         * push the board down by its own height.
         */}
        <nav className="flex items-center gap-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => onTab(t.key)}
              aria-current={tab === t.key ? "page" : undefined}
              className={cn(
                "fig hit relative rounded px-2 py-1 text-[10px] tracking-[0.1em] uppercase",
                tab === t.key ? "text-ink" : "text-ink-4 hover:text-ink-2",
              )}
            >
              {t.label}
              {tab === t.key && (
                <span
                  aria-hidden
                  className="absolute inset-x-1.5 -bottom-[3px] h-[2px] rounded-full"
                  style={{ background: "var(--flip)" }}
                />
              )}
            </button>
          ))}
        </nav>

        {clock && (
          <div className="flex items-baseline gap-2">
            <span className="fig text-[13px] text-ink">{clock.et_time}</span>
            <span className="eyebrow text-[9px]">ET</span>
            <span className="hidden text-[10.5px] text-ink-3 sm:inline">{clock.phase.label}</span>
            {clock.overlap && (
              <span className="fig rounded bg-flip/15 px-1.5 py-px text-[9px] text-flip">
                OVERLAP
              </span>
            )}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <span
            className={cn(
              "h-[7px] w-[7px] rounded-full",
              live ? "bg-call live-dot" : "bg-err",
            )}
            aria-hidden
          />
          <span className="fig text-[9.5px] text-ink-4">{live ? "LIVE" : "OFFLINE"}</span>
          <button
            type="button"
            onClick={onRefresh}
            className="fig hit rounded border border-ring px-2 py-px text-[9.5px] text-ink-4 hover:text-ink-2"
          >
            REFRESH
          </button>
        </div>
      </div>

      {strip.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-ring/60 bg-surface/50 px-3 py-1.5">
          {strip.map((q) => (
            <div key={q.key} className="flex items-baseline gap-1.5">
              <span className="fig text-[9.5px] tracking-wider text-ink-4 uppercase">{q.key}</span>
              <Tick value={num(q.last)} className="fig text-[11.5px] text-ink" />
              <Tick value={pct(q.pct)} className={cn("fig text-[10px]", dir(q.pct))} />
            </div>
          ))}
        </div>
      )}
    </header>
  );
}

/** The two-ring lockup. Chrome hues — decoration, never data. */
function Mark() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 32 32"
      aria-hidden
      className="shrink-0"
      // The mark glows and moves past the viewBox on the beat; without this
      // the SVG clips its own drop-shadow at the edge and the motion reads as
      // a flicker rather than as light.
      style={{ overflow: "visible" }}
    >
      {/*
       * THE PETASOS — the winged helmet, front on, which is what "hermes icon"
       * actually means in every icon set (owner pointed at the search results
       * and asked for it). Chosen over the caduceus and the winged sandal by
       * rendering all of them at 18 pixels and looking: the caduceus mushes
       * into a vertical smudge, the sandal reads as a boot-shaped tick, and
       * the SYMMETRIC helmet survives — symmetry is what miniaturises.
       * Dome and brim in the chrome pair's second hue, two feathers a side in
       * the first.
       */}
      <g className="hermes-wing-l">
        <path
          d="M8.5 18 C 5.5 14.5, 3.5 12.5, 1.5 12"
          fill="none"
          stroke="var(--icon-a)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M9.5 20 C 7 17.5, 5 16.5, 3 16.5"
          fill="none"
          stroke="var(--icon-a)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </g>
      <g className="hermes-wing-r">
        <path
          d="M23.5 18 C 26.5 14.5, 28.5 12.5, 30.5 12"
          fill="none"
          stroke="var(--icon-a)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M22.5 20 C 25 17.5, 27 16.5, 29 16.5"
          fill="none"
          stroke="var(--icon-a)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </g>
      <g className="hermes-helm">
        <path
          d="M8 21 A 8 8 0 0 1 24 21"
          fill="none"
          stroke="var(--icon-b)"
          strokeWidth="2.8"
          strokeLinecap="round"
        />
        <path
          d="M5.5 21 L 26.5 21"
          fill="none"
          stroke="var(--icon-b)"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}
