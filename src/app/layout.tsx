import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { THEME_COOKIE, hue, parseTheme, themeStyle } from "@/lib/theme";
import { HERMES_MARK_D } from "@/lib/hermesMark";
import "./globals.css";

/**
 * The favicon is the same winged-orb lockup as the on-page mark, in the chrome
 * hues — inlined as an SVG data URI so there is no file to keep in step with
 * the palette and no request for 300 bytes.
 */
function icon(a: string, b: string): string {
  // The owner's winged helm (lib/hermesMark.ts). Stroked heavily: in a 16px
  // tab the traced lines alone are under half a pixel and simply vanish.
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">` +
    `<rect width="512" height="512" rx="112" fill="#0a0b10"/>` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/>` +
    `</linearGradient></defs>` +
    `<path fill="url(#g)" stroke="url(#g)" stroke-width="14" transform="translate(51 51) scale(0.8)" d="${HERMES_MARK_D}"/></svg>`
  );
}

/**
 * The tab icon follows the MARK's own two hues, which is why it cannot stay
 * hardcoded: a green-and-pink favicon above a retinted header is the one
 * mismatch guaranteed to be noticed, because both are on screen at once.
 */
export async function generateMetadata(): Promise<Metadata> {
  const jar = await cookies();
  const t = parseTheme(jar.get(THEME_COOKIE)?.value);
  const svg = icon(hue(t.iconA, "green").neon, hue(t.iconB, "pink").neon);
  return {
    ...baseMetadata,
    icons: { icon: `data:image/svg+xml,${encodeURIComponent(svg)}` },
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
