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
      viewBox="0 0 512 512"
      aria-hidden
      className="shrink-0"
      // The mark glows past the viewBox on the breath; without this the SVG
      // clips its own drop-shadow at the edge.
      style={{ overflow: "visible" }}
    >
      {/*
       * THE TALARIA — Hermes' winged sandal, in flight.
       *
       * "Wingfoot" by Lorc, game-icons.net, CC BY 3.0 (attribution in the
       * README). The owner rejected two of my hand-cut marks — rightly; a
       * professional cut is a different thing — and this is the strongest
       * Hermes symbol in the openly licensed catalogues: unmistakably his,
       * pure speed, and it survives 20 pixels where the caduceus goes busy
       * and a bare wing goes generic.
       *
       * ONE PATH, TWO HUES: the art is a single compound path, so the chrome
       * pair rides a gradient across it instead of splitting parts — the same
       * teal-to-magenta the wordmark washes with, which ties the lockup
       * together.
       */}
      <defs>
        <linearGradient id="hermes-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--icon-a)" />
          <stop offset="1" stopColor="var(--icon-b)" />
        </linearGradient>
      </defs>
      <path className="hermes-mark" fill="url(#hermes-grad)" d="m494.25 21.125-164.53 1.25c-15.463 27.984-33.913 52.67-54.163 75.8 6.012 1.497 12.073 2.995 18.027 4.497l13.69 3.453-8.528 11.254c-50.415 66.503-44.632 142.087-27.36 213.694l-18.17 4.383c-16.838-69.817-23.528-148.192 22.64-217.94-88.07-21.897-183.62-43.434-253.374-89.38-1.77 4.89-1.01 10.187 2.262 17.23 2.427 5.222 6.516 11.043 12.14 17.117 53.162 37.938 130.458 65.946 189.778 75.168l-2.87 18.467c-61.85-9.616-139.642-37.397-196.036-77.227.61 5.953 2.61 12.393 6.387 19.36 6.918 12.758 19.275 26.49 35.7 38.907.84.635 1.697 1.265 2.557 1.893 42.555 22.677 93.696 38.914 140.737 42.164l-1.287 18.644c-61.147-4.222-126.33-28.22-175.672-60.745 1.03 4.922 3.253 10.397 6.885 16.38 7.367 12.14 20.078 25.484 36.23 37.675 39.264 17.838 81.604 32.938 128.62 36.473l-1.4 18.636C150.41 244.06 101.38 224.536 57.41 203.57c3.7 19.623 17.285 34.4 38.926 46.805 26.818 15.373 65.26 25.424 105.822 31.328l7.457 1.086.52 7.517c1.074 15.51 4.568 22.832 9.742 31.672l-16.13 9.438c-4.93-8.426-9.286-18.45-11.292-32.436-32.304-5.087-63.402-12.616-89.365-24.265a604.906 604.906 0 0 0-18.994 24.033c16.515 23.758 30.6 43.036 52.78 65.78l27.095-9.467 9.343-3.25 2.718 9.53c15.066 53.052 59.564 93.564 113.595 113.813 48.005 17.99 103.003 19.633 150.063.594-68.673-37.578-114.617-123.708-135.782-199.875l-1.125-4.156 2.376-3.564C348.53 203.283 425.85 148.88 494.25 123.97V21.124z" />
    </svg>
  );
}
