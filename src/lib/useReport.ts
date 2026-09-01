"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReportAsset, ReportFeed, ReportSession } from "@/types/terminal";
import { oneOf, usePersisted } from "./usePersisted";

/**
 * The report tab's state, owned above the tab switch.
 *
 * WHY IT IS NOT IN THE PANEL. The panel unmounts when you leave the tab, and a
 * generation takes two to three minutes on a free model — long enough that
 * switching to the terminal while it runs is the normal thing to do. With the
 * state inside the panel that abandoned the request: the fetch was cancelled,
 * the working state died with the component, and returning to the tab showed
 * the previous report as though nothing had been asked for. Hoisting it here
 * means the promise is owned by something that stays mounted for the life of
 * the page.
 *
 * `seq` GUARDS THE LANDING, not the request. An abandoned generation is still
 * spending tokens upstream and its answer is still worth having, so nothing is
 * aborted — but if two are somehow in flight, only the newest is allowed to
 * write. The same rule the terminal poll uses.
 */

export interface ReportController {
  pick: ReportSession | "auto";
  setPick: (v: ReportSession | "auto") => void;
  book: ReportAsset;
  setBook: (v: ReportAsset) => void;
  feed: ReportFeed | null;
  busy: boolean;
  /** The stored report being viewed, when it is not simply the latest. */
  viewing: string | null;
  generate: () => void;
  open: (id: string) => void;
}

export function useReport(initial: ReportFeed | null): ReportController {
  const [feed, setFeed] = useState<ReportFeed | null>(initial);
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState<string | null>(null);
  const [pick, setPick] = usePersisted<ReportSession | "auto">(
    "report.session",
    "auto",
    oneOf("auto", "asia", "london", "ny"),
  );
  const [book, setBook] = usePersisted<ReportAsset>(
    "report.asset",
    "all",
    oneOf("all", "NQ", "ES", "GC"),
  );
  const seq = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/report", { cache: "no-store" });
      setFeed((await r.json()) as ReportFeed);
    } catch {
      /* the route handler returns an offline body rather than throwing */
    }
  }, []);

  useEffect(() => {
    if (!initial) void refresh();
  }, [initial, refresh]);

  const generate = useCallback(() => {
    setBusy(true);
    setViewing(null);
    const mine = ++seq.current;
    void (async () => {
      try {
        const r = await fetch(`/api/report?session=${pick}&asset=${book}`, {
          method: "POST",
          cache: "no-store",
        });
        const next = (await r.json()) as ReportFeed;
        if (mine === seq.current) setFeed(next);
      } catch {
        /* same */
      } finally {
        if (mine === seq.current) setBusy(false);
      }
    })();
  }, [pick, book]);

  const open = useCallback((id: string) => {
    setViewing(id);
    void (async () => {
      try {
        const r = await fetch(`/api/report/${encodeURIComponent(id)}`, {
          cache: "no-store",
        });
        const next = (await r.json()) as ReportFeed;
        setFeed((f) => (f ? { ...f, latest: next.latest } : next));
      } catch {
        /* same */
      }
    })();
  }, []);

  return { pick, setPick, book, setBook, feed, busy, viewing, generate, open };
}
