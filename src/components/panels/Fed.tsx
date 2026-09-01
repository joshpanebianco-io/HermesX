"use client";

import type { FedEvent } from "@/types/terminal";
import { Module } from "@/components/ui/Module";
import { cn } from "@/lib/cn";

/**
 * The Fed's own diary — who speaks, and when, before they speak.
 *
 * THE WIRE ALREADY CARRIES FED SPEECHES. It carries them afterwards. On this
 * desk's own tape, "Barclays sees two more Fed rate hikes after Warsh speech"
 * and "Warsh's Jackson Hole comments" were both moving the market and the
 * terminal had no way to know either was coming. This panel is the forward
 * half of the same information, straight from the Board's events feed.
 *
 * FORWARD ONLY. A Fed speech that has already happened is a headline, and the
 * wire is where headlines live — repeating it here as a diary entry would be
 * the same fact twice in two voices.
 *
 * THE FOMC IS NOT A SPEECH AND IS NOT DRAWN LIKE ONE. A decision and a press
 * conference stop the tape; a governor at a research conference does not. The
 * amber rail is for the ones that reprice the front of the curve.
 */

const KIND_HUE: Record<string, string> = {
  FOMC: "var(--flip)",
  "Beige Book": "var(--flip)",
  Testimony: "var(--desk-policy)",
  Speech: "var(--desk-macro)",
  Conference: "var(--ink-4)",
};

export function Fed({
  rows,
  today,
  ageMin,
  error,
}: {
  rows: FedEvent[];
  /** The ET date, from the collector — never `new Date()`; see Earnings. */
  today: string;
  ageMin?: number | null;
  error?: string | null;
}) {
  return (
    <Module
      title="Fed diary"
      sub={rows.length ? `next ${rows.length}` : undefined}
      ageMin={ageMin}
      error={error}
      bodyClassName="px-0 py-0"
    >
      {rows.length === 0 ? (
        <p className="px-3 py-5 text-center text-[11px] text-ink-4">
          Nothing scheduled in the next three weeks.
        </p>
      ) : (
        <ul>
          {rows.map((r, i) => {
            const hue = KIND_HUE[r.kind] ?? "var(--ink-4)";
            return (
              <li
                key={`${r.date}-${r.kind}-${i}`}
                className="hit relative flex items-baseline gap-2 py-[3px] pr-3 pl-3.5"
                title={r.note ?? undefined}
              >
                <span
                  aria-hidden
                  className="absolute inset-y-0 left-0 w-[2px]"
                  style={{ background: hue, opacity: r.major ? 1 : 0.4 }}
                />
                <span className="fig w-[52px] shrink-0 text-[10px] text-ink-4">
                  {label(r.date, today)}
                </span>
                <span className="fig w-[38px] shrink-0 text-[10px] text-ink-4">
                  {r.et ?? "—"}
                </span>
                <span
                  className={cn(
                    "min-w-0 flex-1 truncate text-[11px]",
                    r.major ? "text-ink-2" : "text-ink-3",
                  )}
                >
                  {/* The feed titles every speech "Speech - Governor X", which
                      is the kind badge repeated in the text. */}
                  {r.title.replace(/^(?:Speech|Discussion|Testimony)\s*[-–]\s*/i, "")}
                </span>
                <span
                  className="fig hidden shrink-0 text-[9px] uppercase sm:block"
                  style={{ color: hue }}
                >
                  {r.kind === "Beige Book" ? "Beige" : r.kind}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Module>
  );
}

/** "Today", "Tmrw", else "Wed 16". Narrow, because the column is. */
function label(date: string, today: string): string {
  if (!today) return date.slice(5);
  if (date === today) return "Today";
  const d = new Date(`${date}T12:00:00Z`);
  const t = new Date(`${today}T12:00:00Z`);
  const days = Math.round((d.getTime() - t.getTime()) / 86_400_000);
  if (days === 1) return "Tmrw";
  // Built by hand, not by toLocaleDateString: en-US's CLDR pattern for
  // weekday-plus-day with no month is "d E", which renders "16 Wed". The
  // weekday leads in a diary — you scan down the days of the week.
  const wd = d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
  return `${wd} ${d.getUTCDate()}`;
}
