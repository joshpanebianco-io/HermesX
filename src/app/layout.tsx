import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { THEME_COOKIE, hue, parseTheme, themeStyle } from "@/lib/theme";
import "./globals.css";

/**
 * The favicon is the same two-ring lockup as the on-page mark, in the chrome
 * hues — inlined as an SVG data URI so there is no file to keep in step with
 * the palette and no request for 300 bytes.
 */
function icon(a: string, b: string): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
    `<rect width="32" height="32" rx="7" fill="#0a0b10"/>` +
    `<circle cx="12.5" cy="19.5" r="7" fill="none" stroke="${a}" stroke-width="2.8"/>` +
    `<circle cx="22.5" cy="10.5" r="4.8" fill="none" stroke="${b}" stroke-width="2.8"/></svg>`
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
  title: "NewsTerminal — macro, wire and gamma",
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
