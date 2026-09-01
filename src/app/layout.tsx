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
    `<path fill="#000" stroke="#000" stroke-width="14" transform="translate(461 51) scale(-0.8 0.8)" d="${HERMES_MARK_D}"/></svg>`
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
  title: "HERMESX — macro, wire and gamma",
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
