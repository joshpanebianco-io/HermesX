"use client";

import { useState } from "react";
import type { Bias, Report as ReportT, ReportAsset, ReportSession } from "@/types/terminal";
import type { ReportController } from "@/lib/useReport";
import { Module } from "@/components/ui/Module";
import { cn } from "@/lib/cn";

/**
 * The session report — a model's read of the whole terminal.
 *
 * WHAT THIS PANEL IS CAREFUL ABOUT. The owner chose to have the model form the
 * view rather than narrate a deterministic one (see server/newsterminal/
 * report.py). That makes the provenance strip below load-bearing rather than
 * decorative: the model name, the moment, and a link to the exact digest it was
 * shown are the only way to tell a good call from a lucky one later. Nothing
 * here is generated locally — with no key the panel says so and shows nothing,
 * because a fabricated bias rendered in the same frame as a real one is the
 * worst thing this product could do.
 *
 * THE BIAS BAR IS A POSITION, NOT A GAUGE. Five states from bearish to bullish
 * with a mark on a track, because "leaning bearish" is a point on a line and a
 * coloured pill would lose the distance between it and "bearish".
 */

function biasHue(b: Bias): string {
  if (b === "bullish") return "var(--call)";
  if (b === "leaning bullish") return "var(--call-dte)";
  if (b === "bearish") return "var(--put)";
  if (b === "leaning bearish") return "var(--put-dte)";
  return "var(--ink-3)";
}

/**
 * Which session the note is written for.
 *
 * THIS DESK TRADES THREE OF THEM, so the note cannot assume New York. `Auto`
 * resolves from the ET clock to the session that is trading or about to — what
 * pressing Generate almost always means — and the three explicit choices are
 * for writing tomorrow's Asia note this afternoon.
 *
 * The choice reaches the model as a different SYSTEM PROMPT, not as a filter on
 * the data: what leads a session, what hands over to it and how it behaves are
 * all different, and a New York framing at 20:00 ET produces a note about the
 * Fed when the reader is about to trade the Nikkei.
 */
const SESSION_PICKS: { key: ReportSession | "auto"; label: string; title: string }[] = [
  { key: "auto", label: "Auto", title: "Whichever session is trading or about to — from the ET clock" },
  { key: "asia", label: "Asia", title: "18:00–03:00 ET · Nikkei, Hang Seng, USD/JPY" },
  { key: "london", label: "London", title: "03:00–08:00 ET · FTSE, DAX, EUR/USD, Bunds" },
  { key: "ny", label: "NY", title: "09:30–16:00 ET · NQ, ES, the curve, the dollar" },
];

/**
 * STATE LIVES IN `useReport`, ABOVE THE TAB SWITCH, and that is a fix rather
 * than a preference. This panel is unmounted when you leave the tab, so an
 * in-flight generation was being abandoned mid-request: the fetch was
 * cancelled, `busy` was lost with the component, and coming back showed the
 * previous report as though nothing had happened. A generation takes two to
 * three minutes on a free model, which is exactly long enough that switching
 * tabs while it runs is the normal thing to do.
 */
/**
 * Which book the note is about.
 *
 * `All` is the right default when you are deciding WHAT to trade; the three
 * single-asset choices are for when you have already decided and want the
 * note's whole attention on one instrument. Picking one narrows the gamma
 * ladder, the session ranges and the index movers in the digest, and swaps the
 * prompt's driver block — told to write about gold, a model handed the equity
 * blocks will otherwise work through technology's relative strength on the way
 * to a call that has nothing to do with it.
 *
 * It is still ONE request either way, so a focused note costs no more of the
 * free tier's daily allowance than the combined one.
 */
const ASSET_PICKS: { key: ReportAsset; label: string; title: string }[] = [
  { key: "all", label: "All", title: "NQ, ES and GC together — where they agree and where they do not" },
  { key: "NQ", label: "NQ", title: "NQ futures and QQQ · cap-weighted, long duration, the heavy names are the story" },
  { key: "ES", label: "ES", title: "ES futures and SPY · broader, sector rotation and breadth carry more" },
  { key: "GC", label: "GC", title: "GC futures and GLD · real yields, the dollar and geopolitics — not the equity blocks" },
];

export function Report({
  pick,
  setPick,
  book,
  setBook,
  feed,
  busy,
  viewing,
  generate,
  open,
}: ReportController) {
  const [showDigest, setShowDigest] = useState(false);
  const rep = feed?.latest ?? null;
  const enabled = feed?.config?.enabled ?? false;

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-y-auto p-2 xl:grid-cols-[minmax(0,3fr)_minmax(260px,1fr)] xl:overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-col gap-2 xl:overflow-y-auto">
        <Module
          title="Session report"
          sub={
            rep
              ? [rep.asset_label, rep.session_label, rep.et_label]
                  .filter(Boolean)
                  .join(" · ")
              : undefined
          }
          bodyClassName="px-0 py-0"
          right={
            <div className="flex items-center gap-1.5">
              <div className="flex items-center gap-0.5">
                {ASSET_PICKS.map((ap) => (
                  <button
                    key={ap.key}
                    type="button"
                    onClick={() => setBook(ap.key)}
                    title={ap.title}
                    className={cn(
                      "fig hit rounded px-1.5 py-px text-[9.5px] leading-[15px] tracking-wide uppercase",
                      book === ap.key ? "bg-ink/10 text-ink" : "text-ink-4 hover:text-ink-2",
                    )}
                  >
                    {ap.label}
                  </button>
                ))}
              </div>
              <span aria-hidden className="h-3 w-px bg-ring" />
              <div className="flex items-center gap-0.5">
                {SESSION_PICKS.map((sp) => (
                  <button
                    key={sp.key}
                    type="button"
                    onClick={() => setPick(sp.key)}
                    title={sp.title}
                    className={cn(
                      "fig hit rounded px-1.5 py-px text-[9.5px] leading-[15px] tracking-wide uppercase",
                      pick === sp.key ? "bg-ink/10 text-ink" : "text-ink-4 hover:text-ink-2",
                    )}
                  >
                    {sp.label}
                  </button>
                ))}
              </div>
              {feed?.config?.model && (
                <span className="fig hidden text-[9px] text-ink-4 lg:inline">
                  {feed.config.model}
                </span>
              )}
              <button
                type="button"
                onClick={generate}
                disabled={busy || !enabled}
                className={cn(
                  "fig hit rounded border px-2 py-px text-[9.5px] leading-[15px] tracking-wide uppercase",
                  busy || !enabled
                    ? "cursor-not-allowed border-ring text-ink-4"
                    : "border-flip/60 bg-flip/15 text-flip hover:bg-flip/25",
                )}
                title={
                  enabled
                    ? "Read the terminal as it stands now and write a fresh note"
                    : "Needs OPENROUTER_API_KEY"
                }
              >
                {busy ? "Reading…" : "Generate"}
              </button>
            </div>
          }
        >
          {!enabled ? (
            <NoKey model={feed?.config?.model} />
          ) : busy ? (
            <Working />
          ) : !rep ? (
            <Empty />
          ) : rep.error ? (
            <Failed rep={rep} />
          ) : rep.report ? (
            <Body rep={rep} onDigest={() => setShowDigest((v) => !v)} showDigest={showDigest} />
          ) : (
            <Empty />
          )}
        </Module>
      </div>

      <div className="flex min-h-0 min-w-0 flex-col gap-2 xl:overflow-y-auto">
        <Module title="Past calls" sub={`${feed?.history?.length ?? 0} kept`} bodyClassName="px-0 py-0">
          {!feed?.history?.length ? (
            <p className="px-3 py-5 text-center text-[11px] text-ink-4">
              Nothing yet. Reports are kept so you can check the calls against how the
              session actually went.
            </p>
          ) : (
            <ul>
              {feed.history.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => open(h.id)}
                    className={cn(
                      "hit flex w-full flex-col items-start gap-0.5 px-3 py-1.5 text-left",
                      (viewing ?? rep?.id) === h.id && "bg-ink/[0.06]",
                    )}
                  >
                    <div className="flex w-full items-baseline gap-2">
                      <span className="fig text-[10px] text-ink-3">{h.et_label}</span>
                      {h.asset_label && h.asset !== "all" && h.asset_label !== "All three books" && (
                        <span className="fig rounded bg-ink/10 px-1 text-[9px] text-ink-3">
                          {h.asset_label}
                        </span>
                      )}
                      {h.session_label && (
                        <span className="fig text-[9px] text-ink-4">{h.session_label}</span>
                      )}
                      {h.bias && (
                        <span
                          className="fig ml-auto shrink-0 rounded px-1 text-[9px]"
                          style={{
                            color: biasHue(h.bias),
                            background: `color-mix(in oklab, ${biasHue(h.bias)} 18%, transparent)`,
                          }}
                        >
                          {h.bias}
                        </span>
                      )}
                    </div>
                    {h.headline && (
                      <span className="line-clamp-2 text-[10.5px] leading-snug text-ink-2">
                        {h.headline}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Module>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- states */

function NoKey({ model }: { model?: string }) {
  return (
    <div className="space-y-3 px-4 py-5 text-[11.5px] leading-relaxed text-ink-3">
      <p className="text-ink-2">
        The report is written by a model, and no key is set — so there is nothing to show.
      </p>
      <p>
        There is deliberately no local fallback. A bias invented by this app and rendered in
        the same frame as a real one would be indistinguishable from it, which is exactly the
        failure the rest of this terminal is built to avoid.
      </p>
      <ol className="ml-4 list-decimal space-y-1">
        <li>
          Get a free key at{" "}
          <a
            href="https://openrouter.ai/keys"
            target="_blank"
            rel="noreferrer noopener"
            className="text-call underline underline-offset-2"
          >
            openrouter.ai/keys
          </a>
          .
        </li>
        <li>
          Put <code className="text-ink-2">OPENROUTER_API_KEY=sk-or-…</code> in{" "}
          <code className="text-ink-2">.env.local</code>.
        </li>
        <li>
          Restart the collector — <code className="text-ink-2">.\dev.ps1</code>.
        </li>
      </ol>
      <p className="text-ink-4">
        Model: <span className="fig">{model ?? "z-ai/glm-5.2:free"}</span> — free tier, no card.
        Override with <code>NT_REPORT_MODEL</code>. The free tier allows 50 requests a day, or
        1000 once $10 of credit has ever been bought.
      </p>
    </div>
  );
}

function Working() {
  return (
    <div className="px-4 py-8 text-center">
      <div className="fig text-[11.5px] text-ink-2">Reading the terminal…</div>
      <p className="mt-1 text-[10.5px] leading-relaxed text-ink-4">
        The board, the gamma structure, the session ranges, the curve, rotation, the calendar
        and the wire go over in one request.
      </p>
      <p className="mx-auto mt-2 max-w-[46ch] text-[10.5px] leading-relaxed text-ink-4">
        On the free tier this can take a couple of minutes. The free pools are shared with
        every other OpenRouter user, so the first model is often saturated and the request
        falls through to the next one — the finished report names whichever actually answered.
      </p>
    </div>
  );
}

function Empty() {
  return (
    <p className="px-4 py-8 text-center text-[11.5px] text-ink-3">
      No report yet — press <span className="fig text-flip">Generate</span>.
    </p>
  );
}

function Failed({ rep }: { rep: ReportT }) {
  return (
    <div className="space-y-2 px-4 py-4 text-[11.5px] leading-relaxed">
      <p className="text-err">{rep.error}</p>
      {rep.raw && (
        <details className="text-[10.5px] text-ink-4">
          <summary className="cursor-pointer text-ink-3">What the model said instead</summary>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap">{rep.raw}</pre>
        </details>
      )}
      <p className="text-ink-4">
        Nothing is shown above because there is no valid report to show — not because the panel
        is empty.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- the note */

function Body({
  rep,
  showDigest,
  onDigest,
}: {
  rep: ReportT;
  showDigest: boolean;
  onDigest: () => void;
}) {
  const r = rep.report!;
  const hue = biasHue(r.bias);

  return (
    <div>
      {/* ---- the call ------------------------------------------------- */}
      <div className="border-b border-ring/50 px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="fig text-[19px] tracking-tight uppercase" style={{ color: hue }}>
            {r.bias}
          </span>
          <span
            className="flex items-center gap-[3px]"
            title="Conviction 1-5 — how strongly the data supports the call. The model's own confidence, not a probability."
          >
            {[1, 2, 3, 4, 5].map((i) => (
              <span
                key={i}
                className="h-[7px] w-[7px] rounded-full"
                style={{ background: i <= r.conviction ? hue : "var(--ring)" }}
              />
            ))}
            <span className="fig ml-1 text-[10px] text-ink-4">
              {r.conviction}/5 conviction
            </span>
          </span>
        </div>

        {/*
         * NO DIRECTIONAL METER, ON PURPOSE — this line replaced two of them
         * in one day. A five-step bias spectrum drew "what do the 5 bars
         * mean?"; a centre-diverging conviction bar drew "why is only a
         * section colored?". Both times the reader had already understood
         * the WORD (direction, in its hue) and the DOTS (strength, in
         * rating grammar) instantly. The meters were decoration explaining
         * things that were not confusing, at the cost of becoming the
         * confusing thing themselves. If a future hand feels this row needs
         * a gauge, read those two quotes first.
         */}

        <p className="text-[13px] leading-snug text-ink">{r.headline}</p>
        <p className="mt-1 text-[11.5px] leading-relaxed text-ink-3">{r.summary}</p>
      </div>

      {/* ---- why ------------------------------------------------------ */}
      <Section title="Why">
        <ul className="space-y-1.5">
          {r.drivers.map((d, i) => (
            <li key={i} className="relative pl-3">
              <span
                aria-hidden
                className="absolute top-[6px] left-0 h-[6px] w-[6px] rounded-full"
                style={{
                  background:
                    d.direction === "bullish"
                      ? "var(--call)"
                      : d.direction === "bearish"
                        ? "var(--put)"
                        : "var(--ink-4)",
                }}
              />
              <span className="text-[11.5px] leading-snug text-ink-2">{d.point}</span>
              <span className="fig ml-1.5 text-[10.5px] text-ink-4">{d.evidence}</span>
            </li>
          ))}
        </ul>
      </Section>

      {/* ---- expected session ----------------------------------------- */}
      <Section title="How the session should behave">
        <p className="text-[11.5px] leading-relaxed text-ink-2">{r.session_expectation}</p>
      </Section>

      {/* ---- levels ---------------------------------------------------- */}
      <Section title="Levels to watch">
        <ul className="space-y-1">
          {r.levels_to_watch.map((l, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2">
              <span className="fig w-[34px] shrink-0 text-[10.5px] text-ink-4">{l.instrument}</span>
              <span className="fig text-[11.5px] text-ink">{l.level}</span>
              <span className="min-w-0 flex-1 text-[10.5px] text-ink-3">{l.why}</span>
            </li>
          ))}
        </ul>
      </Section>

      {/* ---- what breaks it -------------------------------------------- */}
      <Section title="What would change it">
        <ul className="space-y-1">
          {r.invalidation.map((v, i) => (
            <li key={i} className="text-[11.5px] leading-snug">
              <span className="text-ink-2">{v.condition}</span>
              <span className="text-ink-4"> → </span>
              <span style={{ color: biasHue(v.flips_to as Bias) }}>{v.flips_to}</span>
            </li>
          ))}
        </ul>
      </Section>

      {r.risks?.length > 0 && (
        <Section title="Risks">
          <ul className="space-y-0.5">
            {r.risks.map((x, i) => (
              <li key={i} className="text-[11px] leading-snug text-ink-3">
                · {x}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ---- provenance ------------------------------------------------ */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ring/50 bg-surface-2/30 px-4 py-2 text-[9.5px] text-ink-4">
        <span className="fig">{rep.model}</span>
        <span aria-hidden>·</span>
        <span className="fig">{rep.asset_label}</span>
        <span aria-hidden>·</span>
        <span className="fig">{rep.session_label} session</span>
        <span aria-hidden>·</span>
        <span className="fig">{rep.et_label}</span>
        {rep.usage?.total_tokens && (
          <>
            <span aria-hidden>·</span>
            <span className="fig">{rep.usage.total_tokens} tok</span>
          </>
        )}
        <button
          type="button"
          onClick={onDigest}
          className="fig ml-auto rounded border border-ring px-1.5 py-px text-[9px] hover:text-ink-2"
        >
          {showDigest ? "Hide" : "Show"} the data it saw
        </button>
      </div>

      {showDigest && (
        <pre className="max-h-[420px] overflow-auto border-t border-ring/50 bg-void/50 px-4 py-2 text-[9.5px] leading-relaxed text-ink-3">
          {JSON.stringify(rep.digest, null, 1)}
        </pre>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-ring/40 px-4 py-2.5 last:border-b-0">
      <div className="eyebrow mb-1.5 text-[9px]">{title}</div>
      {children}
    </div>
  );
}

/** Five pips. The model's own confidence, which is not a probability. */
