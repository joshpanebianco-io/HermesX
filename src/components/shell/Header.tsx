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
      width="20"
      height="20"
      viewBox="0 0 32 32"
      aria-hidden
      className="shrink-0"
      // The mark glows and moves past the viewBox on the beat; without this
      // the SVG clips its own drop-shadow at the edge and the motion reads as
      // a flicker rather than as light.
      style={{ overflow: "visible" }}
    >
      {/*
       * THE GOD HIMSELF, IN PROFILE — the owner pointed at the stock-vector
       * genre (classical head, winged helm, emblem cut) and asked for that
       * over the bare hat. Hand-cut and auditioned at chip size like its
       * predecessors: the full striding figure dies into a pedestrian-crossing
       * sprite at 18px, but a PROFILE head survives, because the forehead
       * flowing straight into the nose is what makes two centimetres of
       * silhouette read as Greek. Face in the chrome pair's second hue; helm
       * and wing in the first.
       *
       * DRAW ORDER IS LOAD-BEARING: face, then wing, then helmet, so the
       * wing's root tucks UNDER the dome and the feathers emerge from the
       * helmet's edge — drawn on top, they grew through it.
       */}
      <path
        className="hermes-head"
        d="M19.6 13.0 L 23.6 17.8 L 22.3 18.6 L 23.2 19.7 L 22.3 20.4 L 23.0 21.4 Q 23.0 22.6 22.2 23.4 Q 20.6 25.2 17.2 25.8 L 16.9 28.8 L 11.6 28.8 Q 12.2 26.0 12.0 23.6 Q 10.4 20.6 10.6 17.2 L 11.2 14.2 Z"
        fill="var(--icon-b)"
      />
      <path
        className="hermes-wing"
        d="M15.5 11.5 C 11.0 10.2, 6.8 8.6, 2.2 5.6 C 4.8 8.6, 6.4 9.9, 8.8 11.1 C 6.0 10.7, 3.2 10.3, 0.9 9.9 C 3.4 11.9, 5.8 12.9, 8.8 13.4 C 6.8 13.6, 4.8 13.9, 2.8 14.4 C 6.2 15.9, 11.2 15.7, 14.6 14.4 Z"
        fill="var(--icon-a)"
      />
      <path
        className="hermes-helm"
        d="M23.2 12.1 Q 24.2 12.4 23.4 11.4 Q 20.6 5.4 13.6 5.9 Q 8.3 6.4 9.3 13.9 Q 9.5 14.8 10.4 14.4 Q 16.0 11.4 21.6 12.2 Z"
        fill="var(--icon-a)"
      />
    </svg>
  );
}
