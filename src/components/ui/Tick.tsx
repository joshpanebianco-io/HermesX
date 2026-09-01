"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * A figure that flashes when it CHANGES, and only then.
 *
 * PORTED FROM GEXYGEN, mechanism unchanged, so the two surfaces cannot drift
 * into different ideas of what "changed" means or how long the flash runs.
 *
 * WHY RE-KEYING. A CSS animation only replays on remount, so the span is keyed
 * by a counter that advances when the rendered value differs from the last
 * one. Comparing the FORMATTED value rather than the raw number is deliberate:
 * a figure that rounds to the same string has not visibly changed, and
 * flashing it would be a lie about the data moving. It also matters more here
 * than it did there — this terminal polls 50-odd instruments every 20 seconds
 * and most of them print an identical string each time.
 *
 * `tick` STAYS 0 THROUGH THE FIRST RENDER, so a page load does not open with
 * the whole terminal flashing at once. That guard is why this is a component
 * rather than a bare className.
 *
 * KEY THE ROW BY ITS IDENTITY, NOT BY ITS VALUE, wherever this is used inside
 * a list. GEXYGEN's Major Walls card keyed wall rows by strike price, so the
 * moment a wall moved to a different strike React unmounted the row and
 * mounted a fresh one — correct React, and it silently defeated the flash,
 * because a remounted `Tick` has no memory of a previous value. The one figure
 * most worth flashing was the only one that never could.
 *
 * ONLY PRIMITIVES PARTICIPATE. A caller passing JSX simply never flashes,
 * which is the correct failure — better silent than flashing on a comparison
 * that cannot be made.
 *
 * The glitch half comes from an ancestor class: `.tick` alone is the glow, and
 * `.fx-glitch-subtle .tick` swaps in the keyframes that glitch first and then
 * perform the identical decay. See the long note in globals.css for why that
 * is one animation rather than two layered.
 */
export function Tick({
  value,
  className,
  title,
  style,
  children,
}: {
  /** The comparison key — pass the FORMATTED figure, not the raw number. */
  value: string | number | null | undefined;
  className?: string;
  title?: string;
  /** For figures whose hue is computed rather than a class — see Volatility. */
  style?: React.CSSProperties;
  /** Defaults to rendering `value`; pass children to decorate it. */
  children?: React.ReactNode;
}) {
  const comparable =
    typeof value === "string" || typeof value === "number" ? value : null;
  const prev = useRef(comparable);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (comparable !== null && prev.current !== comparable) {
      prev.current = comparable;
      setTick((n) => n + 1);
    }
  }, [comparable]);

  return (
    <span key={tick} className={cn(tick > 0 && "tick", className)} title={title} style={style}>
      {children ?? value}
    </span>
  );
}
