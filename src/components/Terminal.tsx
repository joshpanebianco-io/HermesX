"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReportFeed, Terminal as TerminalData } from "@/types/terminal";
import { Header } from "@/components/shell/Header";
import { StatusRail } from "@/components/shell/StatusRail";
import { Wire } from "@/components/panels/Wire";
import { Board } from "@/components/panels/Board";
import { Gamma } from "@/components/panels/Gamma";
import { Rates } from "@/components/panels/Rates";
import { Rotation } from "@/components/panels/Rotation";
import { Calendar } from "@/components/panels/Calendar";
import { Sessions } from "@/components/panels/Sessions";
import { Report } from "@/components/panels/Report";
import { Settings } from "@/components/panels/Settings";
import { SessionRanges } from "@/components/panels/SessionRanges";
import { Earnings } from "@/components/panels/Earnings";
import { Movers } from "@/components/panels/Movers";
import { Volatility } from "@/components/panels/Volatility";
import { Fed } from "@/components/panels/Fed";
import { AlertStrip } from "@/components/shell/AlertStrip";
import { DEFAULT_THEME, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/cn";
import { useReport } from "@/lib/useReport";
import { useFrameLight, type FrameFx } from "@/lib/useFrameLight";
import { oneOf, usePersisted } from "@/lib/usePersisted";

/**
 * The terminal.
 *
 * THREE COLUMNS, AND THE MIDDLE ONE IS THE WIRE. The layout encodes what this
 * product is for: context on the left (the clock, the gamma structure, the
 * curve), news in the middle where the eye rests, prices and rotation on the
 * right. A four-column grid of equal panes would be prettier and would say
 * nothing about which of them you are meant to be reading.
 *
 * THE CHASSIS IS EXACTLY ONE VIEWPORT AND THE COLUMNS SCROLL INSIDE IT.
 *
 * The first cut let the page grow and scroll as a whole, which read fine until
 * you noticed the status rail had scrolled off the bottom — the one element
 * that must never be out of sight, because it is the only thing that says
 * whether what you are looking at is live. A terminal's state line is pinned
 * or it is decoration.
 *
 * Three scroll regions rather than nine: the columns, not the panels. The
 * right-hand column alone is around 1700px of board and calendar, so something
 * has to scroll; doing it per COLUMN keeps each one a single continuous
 * reading position instead of turning the grid into a filing cabinet of
 * independently-lost boxes.
 *
 * THE CLOCK TICKS LOCALLY. Polling at twenty seconds would give a session
 * countdown that jumps in twenty-second steps, which looks broken. The payload
 * carries the collector's ET instant; this advances it locally each second and
 * lets the next poll correct any drift.
 */

const POLL_SEC = Number(process.env.NEXT_PUBLIC_POLL_SEC ?? 20);

type Tab = "terminal" | "report" | "settings";

export function Terminal({
  initial,
  initialReport,
  initialTab = "terminal",
  initialTheme = DEFAULT_THEME,
}: {
  initial: TerminalData;
  initialReport: ReportFeed | null;
  initialTab?: Tab;
  initialTheme?: ThemeChoice;
}) {
  // Held here rather than in Settings so the tab can be left and returned to
  // without the picker forgetting what is selected. The cookie is the durable
  // copy; this is only what the open page believes.
  const [theme, setTheme] = useState<ThemeChoice>(initialTheme);

  /*
   * The report's state is owned HERE rather than in its panel, so a generation
   * survives switching tabs — see `useReport`. It takes minutes on a free
   * model, and the panel unmounting was cancelling it.
   */
  const report = useReport(initialReport);

  /*
   * The chassis light. Held here because the frame it draws on lives here, and
   * persisted so the choice survives a reload like every other preference.
   * `useFrameLight` only drives "travel" — breathe is pure CSS and off hides
   * the ring, and for both the hook stands down and cancels any comet left
   * running from a live switch.
   */
  const [fx, setFx] = usePersisted<FrameFx>(
    "frame.fx",
    "travel",
    oneOf("off", "travel", "breathe"),
  );
  const frameRef = useRef<HTMLDivElement | null>(null);
  useFrameLight(frameRef, fx);
  /*
   * The URL wins over storage when it says something. `?tab=report` is an
   * explicit instruction from whoever followed the link; the remembered tab is
   * only what this browser last looked at, and a deep link that silently landed
   * somewhere else would be worse than not remembering at all.
   */
  const [storedTab, setStoredTab] = usePersisted<Tab>(
    "tab",
    initialTab,
    oneOf("terminal", "report", "settings"),
  );
  const [tab, setTabState] = useState<Tab>(initialTab);
  const urlPinned = useRef(initialTab !== "terminal");
  useEffect(() => {
    if (!urlPinned.current && storedTab !== tab) setTabState(storedTab);
    // Runs when storage lands after mount; a later user click owns it from
    // then on and this must not fight them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storedTab]);

  /*
   * The tab is written to the URL with replaceState rather than a navigation.
   * Both tabs are already mounted with their data in hand, so routing would
   * re-run the server component and re-fetch the collector to show something
   * the client is holding — all to change one query parameter.
   */
  const setTab = useCallback((t: Tab) => {
    setTabState(t);
    setStoredTab(t);
    urlPinned.current = false;
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      if (t === "terminal") u.searchParams.delete("tab");
      else u.searchParams.set("tab", t);
      window.history.replaceState(null, "", u);
    }
  }, [setStoredTab]);
  const [data, setData] = useState<TerminalData>(initial);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);
  /*
   * NULL UNTIL MOUNTED, and that is the whole point.
   *
   * The server has no business guessing the reader's wall clock: rendering a
   * locally-computed time during SSR produced a different string on the server
   * and on the client, which is a hydration mismatch on every single load —
   * React discards the server subtree and re-renders it, and the dev overlay
   * counts an issue. Staying null through the first render means the server's
   * clock is what hydrates, and the local second-hand only starts afterwards.
   */
  const [now, setNow] = useState<number | null>(null);
  // Guards against a slow response landing after a newer one — with a fixed
  // interval and a variable round trip this is not hypothetical.
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const r = await fetch("/api/terminal", { cache: "no-store" });
      const next = (await r.json()) as TerminalData;
      if (mine === seq.current) {
        setData(next);
        setLastPoll(new Date());
      }
    } catch {
      // The route handler already turns a dead collector into a body with an
      // `offline` block; reaching here means the Next server itself is gone,
      // and the previous payload with its ages climbing is the honest render.
    }
  }, []);

  useEffect(() => {
    const id = setInterval(load, POLL_SEC * 1000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const clock = useMemo(() => localClock(data.clock, now), [data.clock, now]);
  const st = data.status ?? {};
  const ages = data.age_min ?? {};

  return (
    <div className="h-screen overflow-hidden p-2 sm:p-3">
      <div
        ref={frameRef}
        className={cn(
          "app-frame flex h-full w-full flex-col overflow-hidden",
          `fx-${fx}`,
          // Every figure that changes glitches before it glows. Subtle is the
          // whole useful range at this type size — see the note in globals.css
          // — so it is a constant rather than another switch in Settings.
          "fx-glitch-subtle",
        )}
      >

        <Header
          clock={clock}
          quotes={data.quotes ?? []}
          live={!data.offline && data.ok}
          onRefresh={load}
          tab={tab}
          onTab={setTab}
        />

        <AlertStrip items={data.wire ?? []} now={now} />

        {data.offline && (
          <div className="border-b border-err/40 bg-err/10 px-3 py-2 text-[11px] text-err">
            <strong className="font-semibold">Collector offline.</strong> {data.offline.reason} —
            expected at <code>{data.offline.api}</code>. Every panel below is empty because there is
            nothing behind it; nothing here is cached or fabricated. Start it with{" "}
            <code className="text-ink-2">.\dev.ps1</code>.
          </div>
        )}

        {tab === "settings" ? (
          <Settings theme={theme} onTheme={setTheme} fx={fx} onFx={setFx} />
        ) : tab === "report" ? (
          <Report {...report} />
        ) : (
        <main className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-y-auto p-2 xl:grid-cols-[minmax(300px,1fr)_minmax(420px,1.35fr)_minmax(320px,1.1fr)] xl:overflow-hidden">
          {/* ---- left: the context the news is read against ------------- */}
          <div className="flex min-h-0 min-w-0 flex-col gap-2 xl:overflow-y-auto">
            {/*
             * ORDERED BY WHAT YOU ACT ON, not by what orients you. The two
             * panels you trade against lead: where price sits inside each
             * session's range is the handover read this terminal exists for,
             * and the seven gamma levels are the prices you place orders at.
             *
             * The session clock earns third rather than first because the
             * header already carries the ET time and the phase ("NY midday"),
             * so what this panel uniquely adds is the city table and the NEXT
             * marker — reference you consult, not a figure you act on. It is
             * still comfortably above the fold at this position.
             *
             * Rates sits last DESPITE being an explicit requirement, because it
             * is the only panel here whose data is daily: the curve stamps a
             * date, not a time, and it cannot move during a session. The vol
             * term structure above it reprices every twenty seconds. Ordering
             * by how often something can change you is the only ordering that
             * survives contact with a fold.
             */}
            <SessionRanges
              assets={data.ranges?.assets ?? {}}
              expiry={data.expiry}
              ageMin={ages.ranges}
              error={st.ranges?.ok === false ? st.ranges.error : null}
            />
            <Gamma
              assets={data.gex?.assets ?? {}}
              enabled={data.gex?.enabled ?? false}
              ageMin={ages.gex}
              error={st.gex?.ok === false ? st.gex.error : null}
            />
            {clock && <Sessions clock={clock} />}
            <Volatility vol={data.volterm} ageMin={ages.quotes} />
            <Rates
              rates={data.rates}
              pm={data.policy_meetings}
              ageMin={ages.rates}
              error={st.rates?.ok === false ? st.rates.error : null}
            />
          </div>

          {/* ---- middle: the wire --------------------------------------- */}
          <div className="flex min-h-0 min-w-0 flex-col gap-2">
            <Wire
              items={data.wire ?? []}
              now={now}
              ageMin={ages.wire}
              error={st.wire?.ok === false ? st.wire.error : null}
            />
          </div>

          {/* ---- right: prices and rotation ----------------------------- */}
          <div className="flex min-h-0 min-w-0 flex-col gap-2 xl:overflow-y-auto">
            <Board
              title="The book"
              quotes={data.quotes ?? []}
              groups={["core"]}
              ageMin={ages.quotes}
              error={st.quotes?.ok === false ? st.quotes.error : null}
            />
            <Movers
              indices={data.constituents?.indices ?? {}}
              ageMin={ages.constituents}
              error={st.constituents?.ok === false ? st.constituents.error : null}
            />
            {/*
             * LIVE STATE FIRST, THEN WHAT IS SCHEDULED. This column used to run
             * prices, movers, calendar, fed, earnings, rotation, macro — which
             * interleaves two different kinds of thing and strands two live
             * panels BELOW three forward-looking ones. Sector rotation was
             * sixth of seven, behind a 221-row calendar, so a regime read the
             * owner asked for by name was the least reachable thing on screen.
             *
             * The split is now clean: what the market is doing right now
             * (prices, the names driving the index, which sectors are bid) sits
             * above the fold, and what is merely on the diary sits below it.
             */}
            <Rotation
              rows={data.sectors ?? []}
              ageMin={ages.sectors}
              error={st.sectors?.ok === false ? st.sectors.error : null}
            />
            <Calendar
              rows={data.calendar ?? []}
              ageMin={ages.calendar}
              error={st.calendar?.ok === false ? st.calendar.error : null}
            />
            <Fed
              rows={data.fed ?? []}
              today={data.expiry?.today ?? ""}
              ageMin={ages.fed}
              error={st.fed?.ok === false ? st.fed.error : null}
            />
            <Earnings
              rows={data.earnings ?? []}
              today={data.expiry?.today ?? ""}
              ageMin={ages.earnings}
              error={st.earnings?.ok === false ? st.earnings.error : null}
            />
            <Board
              title="Macro board"
              quotes={data.quotes ?? []}
              groups={["vol", "energy", "rates", "fx", "metals", "global", "crypto"]}
              ageMin={ages.quotes}
            />
          </div>
        </main>
        )}

        <StatusRail status={st} ages={ages} pollSec={POLL_SEC} lastPoll={lastPoll} />
      </div>
    </div>
  );
}

/**
 * The payload's clock, advanced locally between polls.
 *
 * `now === null` means "first render, before mount" and returns the collector's
 * own clock untouched — see the note on the `now` state above.
 *
 * Only the displayed time and the countdowns move; open/closed and the phase
 * stay as the collector computed them, because recomputing a session boundary
 * in the browser would need the whole zone table and would be a second
 * implementation that could disagree with the first.
 */
function localClock(clock: TerminalData["clock"] | undefined, now: number | null) {
  if (!clock) return null;
  const base = Date.parse(clock.et);
  if (now === null || Number.isNaN(base)) return clock;

  const elapsedMin = (now - base) / 60000;
  return {
    ...clock,
    et_time: new Date(now).toLocaleTimeString("en-US", {
      hour12: false,
      timeZone: "America/New_York",
    }),
    sessions: clock.sessions.map((s) => ({
      ...s,
      next_min: Math.max(0, s.next_min - elapsedMin),
    })),
    markers: clock.markers.map((m) => ({
      ...m,
      in_min: Math.max(0, m.in_min - elapsedMin),
    })),
  };
}
