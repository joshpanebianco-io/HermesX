import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { THEME_COOKIE, parseTheme, themeStyle } from "@/lib/theme";
import { HERMES_MARK_D } from "@/lib/hermesMark";
import "./globals.css";

/**
 * The favicon is the same winged-helm mark as the header, cut as a plain
 * black glyph — inlined as an SVG data URI so there is no file to keep in
 * step and no request for it.
 */
function icon(): string {
  // JUST BLACK, at the owner's ask (2026-09-01) — a plain black glyph on a
  // transparent tile, the way most site favicons are cut, so it no longer
  // follows the theme hues. Mirrored to match the header. The stroke is what
  // keeps sub-pixel line art alive in a 16px tab. If it ever disappears
  // against a dark browser theme, the one-line fix is a light fill here.
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">` +
    // Full-bleed: a browser renders the tab icon at 16px regardless, so the
    // only way to make it BIGGER is to stop paying margins inside the tile
    // (was 80% with a border of dead space). Stroke up a step for the same
    // reason — presence at sixteen pixels.
    // tx 586 is OPTICAL centring, not geometric: at 570 the measured gaps
    // were already 1/2 — balanced — and the owner still read it as sitting
    // left, because the helm's solid mass is left and the wing is sparse
    // line work. 9px of deliberate right bias (per 256) is what makes the
    // MASS look centred.
    // Scale 1.18 is PAST full bleed and crops on purpose (owner asked for
    // bigger twice after the edges were already touching): the top feather
    // flattens a hair against the tile and reads as a deliberate crop, not
    // damage. Grown about the art's own centre from the measured-centred
    // 1.1/translate(550 -26), so the earlier 10/9 balance carries over.
    // Another size step (owner): the trace carries a 22-unit internal margin
    // inside its 512 box, so growing past scale 1.0 is what actually cancels
    // it — 1.06 fills the tile edge to edge without the rotated wing tips
    // clipping. Tilt matches the header: rotate leftmost = screen space.
    `<path fill="#000" stroke="#000" stroke-width="20" transform="rotate(-10 256 256) translate(586 -46) scale(-1.18 1.18)" d="${HERMES_MARK_D}"/></svg>`
  );
}

/*
 * THE TAB ICON USED TO FOLLOW THE THEME HUES, and the machinery for that —
 * cookie read, theme parse, per-request metadata — came out when the owner
 * asked for a plain black glyph (2026-09-01). Static art, static metadata.
 */
export function generateMetadata(): Metadata {
  return {
    ...baseMetadata,
    icons: { icon: `data:image/svg+xml,${encodeURIComponent(icon())}` },
  };
}

const baseMetadata: Metadata = {
  title: "HERMESX — News Terminal",
  description:
    "A single-desk market terminal: the wire, the board, the curve, sector rotation, " +
    "the economic calendar and borrowed gamma levels, on one session clock.",
};

export const viewport: Viewport = {
  themeColor: "#0a0b10",
  width: "device-width",
  initialScale: 1,
};

/**
 * THE THEME GOES ON `<html>`, AND IT HAS TO.
 *
 * Anything reading a token with `getComputedStyle` reads it from the document
 * element, so custom properties written to a nested wrapper would style the DOM
 * and leave those readers on the compiled defaults — the same trap GEXYGEN
 * documents for its canvas panes. Server-side, so the first paint is already
 * themed rather than flashing the default palette and switching.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const jar = await cookies();
  const theme = parseTheme(jar.get(THEME_COOKIE)?.value);
  return (
    <html lang="en" style={themeStyle(theme)}>
      <body>{children}</body>
    </html>
  );
}
