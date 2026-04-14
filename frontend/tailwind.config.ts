import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Arukai brand tokens
        "bg-bone": "#FAFAF8",
        "bg-parchment": "#EEE9E0",
        "bg-obsidian": "#0D0F12",
        "bg-graphite": "#1A1F28",
        "fg-obsidian": "#0D0F12",
        "fg-slate": "#5B6472",
        "fg-muted": "#8C95A3",
        "brand-brass": "#B8914E",
        "brand-brass-pressed": "#9A7639",
        "data-positive": "#1F7A4D",
        "data-negative": "#B23A2E",
        "border-hairline": "rgba(26,31,40,0.10)",
      },
      fontFamily: {
        display: ["'Cormorant Garamond'", "Georgia", "serif"],
        interface: ["'DM Sans'", "system-ui", "sans-serif"],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
      transitionDuration: {
        fast: "150ms",
        standard: "240ms",
      },
    },
  },
  plugins: [],
};

export default config;
