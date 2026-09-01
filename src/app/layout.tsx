import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { THEME_COOKIE, hue, parseTheme, themeStyle } from "@/lib/theme";
import "./globals.css";

/**
 * The favicon is the same winged-orb lockup as the on-page mark, in the chrome
 * hues — inlined as an SVG data URI so there is no file to keep in step with
 * the palette and no request for 300 bytes.
 */
function icon(a: string, b: string): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
    `<rect width="32" height="32" rx="7" fill="#0a0b10"/>` +
    `<path d="M19.6 13.0 L 23.6 17.8 L 22.3 18.6 L 23.2 19.7 L 22.3 20.4 L 23.0 21.4 Q 23.0 22.6 22.2 23.4 Q 20.6 25.2 17.2 25.8 L 16.9 28.8 L 11.6 28.8 Q 12.2 26.0 12.0 23.6 Q 10.4 20.6 10.6 17.2 L 11.2 14.2 Z" fill="${b}"/>` +
    `<path d="M15.5 11.5 C 11.0 10.2, 6.8 8.6, 2.2 5.6 C 4.8 8.6, 6.4 9.9, 8.8 11.1 C 6.0 10.7, 3.2 10.3, 0.9 9.9 C 3.4 11.9, 5.8 12.9, 8.8 13.4 C 6.8 13.6, 4.8 13.9, 2.8 14.4 C 6.2 15.9, 11.2 15.7, 14.6 14.4 Z" fill="${a}"/>` +
    `<path d="M23.2 12.1 Q 24.2 12.4 23.4 11.4 Q 20.6 5.4 13.6 5.9 Q 8.3 6.4 9.3 13.9 Q 9.5 14.8 10.4 14.4 Q 16.0 11.4 21.6 12.2 Z" fill="${a}"/></svg>`
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
