"use client";

import { useEffect, type RefObject } from "react";

/**
 * Drives the frame's travelling light at a constant speed along the border.
 *
 * PORTED FROM GEXYGEN, which is where the geometry was worked out. Kept as a
 * copy rather than shared because the two projects are separate repos and the
 * only thing that differs is RADIUS — a dependency between them for one
 * constant would cost more than it saves.
 *
 * THE PAINT IS STILL CSS — the masked conic ring in `.app-frame::after`, which
 * is what makes it look like light: a conic gradient interpolates per pixel, so
 * the head-to-tail fade is genuinely smooth. An SVG stroked-dash version was
 * tried and reverted for exactly that reason. It had perfect uniform speed, but
 * SVG gradients are spatial rather than along-path, so its fade had to be built
 * from stacked dashes — and five discrete opacity steps with a hard edge where
 * each dash ends is banding, not a fade.
 *
 * ONLY THE TIMING MOVED HERE. A conic gradient sweeps at a constant ANGULAR
 * rate, and a rectangle's perimeter is not equidistant from its centre: the
 * arc-length rate is r²/h, so a linear angle crawls the edge midpoints and
 * accelerates through the corners. Measured before this: 2.5x at the corners
 * against the top edge on the Strike Map (1840x1481), and 13.4x on Settings
 * (1840x522).
 *
 * WHY IT CANNOT BE A FIXED EASING FUNCTION. The distortion is a function of the
 * frame's aspect ratio, and this frame's height changes with every tab — 522px
 * against 1481px above. One `cubic-bezier` or `linear()` curve cannot be right
 * for both. So the curve is GENERATED from the measured box: walk the rounded
 * rectangle in equal steps of arc length, record the angle each step sits at,
 * and emit those angles as keyframes. Linear interpolation between them is then
 * linear in DISTANCE rather than in angle, which is the whole fix.
 *
 * A ResizeObserver rebuilds it, because a curve computed for one tab's frame is
 * wrong for the next one's.
 */

/** One lap, ms. */
const LAP_MS = 10_000;

/**
 * Angle samples per lap. The error is the gap between the true arc-length curve
 * and the straight line drawn between two samples; 180 puts a sample every 2
 * degrees, which is far below what reads as motion.
 */
const SAMPLES = 180;

/**
 * `.app-frame`'s border-radius. The ring rides the border box, so this is it.
 *
 * 14 here against GEXYGEN's 16 — this chassis is a slightly tighter corner.
 * It has to match `globals.css` or the generated curve corrects for a corner
 * the frame does not have, which shows up as the light easing at the wrong
 * moment rather than as anything obviously broken.
 */
const RADIUS = 14;

/** A point on the rounded rectangle at arc length `s`, in centre-origin coords. */
function pointAt(
  s: number,
  a: number,
  b: number,
  r: number,
  sx: number,
  sy: number,
  arc: number,
): [number, number] {
  const q = Math.PI / 2;
  if (s < sx) return [-a + r + s, -b]; // top, left to right
  s -= sx;
  if (s < arc) {
    const t = (s / arc) * q; // top-right corner
    return [a - r + r * Math.sin(t), -b + r - r * Math.cos(t)];
  }
  s -= arc;
  if (s < sy) return [a, -b + r + s]; // right, top to bottom
  s -= sy;
  if (s < arc) {
    const t = (s / arc) * q; // bottom-right corner
    return [a - r + r * Math.cos(t), b - r + r * Math.sin(t)];
  }
  s -= arc;
  if (s < sx) return [a - r - s, b]; // bottom, right to left
  s -= sx;
  if (s < arc) {
    const t = (s / arc) * q; // bottom-left corner
    return [-a + r - r * Math.sin(t), b - r + r * Math.cos(t)];
  }
  s -= arc;
  if (s < sy) return [-a, b - r - s]; // left, bottom to top
  s -= sy;
  const t = (s / arc) * q; // top-left corner, back to the start
  return [-a + r - r * Math.cos(t), -b + r - r * Math.sin(t)];
}

/** Keyframes whose angle advances with DISTANCE around the border, not with time. */
function arcLengthKeyframes(w: number, h: number, r: number): Keyframe[] {
  const a = w / 2;
  const b = h / 2;
  const sx = 2 * (a - r); // top and bottom edges
  const sy = 2 * (b - r); // left and right edges
  const arc = (Math.PI / 2) * r;
  const perimeter = 2 * sx + 2 * sy + 4 * arc;

  const out: Keyframe[] = [];
  let last: number | null = null;
  let turns = 0;

  for (let i = 0; i <= SAMPLES; i++) {
    const [x, y] = pointAt((i / SAMPLES) * perimeter, a, b, r, sx, sy, arc);
    /*
     * `conic-gradient` measures from twelve o'clock and increases clockwise,
     * while the y axis points down — so the angle is atan2(x, -y), not the
     * atan2(y, x) that would give the usual maths convention.
     */
    let deg = (Math.atan2(x, -y) * 180) / Math.PI;
    if (deg < 0) deg += 360;
    // Unwrap. Keyframes have to climb monotonically or the light snaps
    // backwards each time the angle crosses due north.
    if (last !== null && deg < last) turns += 1;
    last = deg;
    out.push({
      offset: i / SAMPLES,
      "--border-angle": `${(deg + turns * 360).toFixed(3)}deg`,
    } as Keyframe);
  }
  return out;
}

/** The three chassis-light modes. */
export type FrameFx = "off" | "travel" | "breathe";

export function useFrameLight(
  ref: RefObject<HTMLElement | null>,
  /**
   * Only "travel" is driven from here — the comet needs the measured-geometry
   * WAAPI animation this hook exists for. "breathe" is pure CSS (`.fx-breathe`
   * in globals.css) and "off" hides the ring, so for both the hook stands down
   * and cancels any comet animation left running from a live mode switch.
   */
  mode: FrameFx = "travel",
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (mode !== "travel") return;
    /*
     * The global `prefers-reduced-motion` block in globals.css collapses CSS
     * animation durations and cannot touch a WAAPI animation, so honouring it is
     * this hook's job. That rule says "no exceptions, including charts".
     */
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let anim: Animation | null = null;
    let last = "";

    const build = () => {
      const { width, height } = el.getBoundingClientRect();
      // Rounded to the pixel: the observer fires on sub-pixel churn, and every
      // rebuild restarts the lap from the top.
      const key = `${Math.round(width)}x${Math.round(height)}`;
      if (key === last) return;
      if (width < 2 * RADIUS || height < 2 * RADIUS) return;
      last = key;
      anim?.cancel();
      anim = el.animate(arcLengthKeyframes(width, height, RADIUS), {
        duration: LAP_MS,
        iterations: Infinity,
        easing: "linear",
        // The gradient lives on the pseudo-element, so the property has to be
        // animated there — it is declared `inherits: false`.
        pseudoElement: "::after",
      });
    };

    build();
    const ro = new ResizeObserver(build);
    ro.observe(el);
    return () => {
      ro.disconnect();
      anim?.cancel();
    };
  }, [ref, mode]);
}
