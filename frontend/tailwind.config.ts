import type { Config } from "tailwindcss";

// NOTE: Tailwind CSS v4 is configured primarily in CSS via the `@theme`
// directive in src/app/globals.css (that is where the design tokens and the
// `dark` variant live). This file is kept for editor tooling and to document
// the content sources and the class-based dark-mode strategy used by
// next-themes.
const config: Config = {
  darkMode: "class",
  content: ["./src/app/**/*.{ts,tsx}", "./src/components/**/*.{ts,tsx}"],
};

export default config;
