import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // RR Design System — exact values from Reddington_System.html
        rr: {
          obsidian: "#0A0A0A",
          charcoal: "#141414",
          steel: "#1E1E1E",
          muted: "#2A2A2A",
          border: "#333333",
          subtle: "#4A4A4A",
          text: "#E8E0D0",
          dim: "#A09888",
          cream: "#F5F0E8",
          brass: "#C8A24A",
          "brass-light": "#D4B060",
          "brass-dark": "#A07830",
          oxblood: "#8B1A1A",
          sage: "#4A7A5A",
          slate: "#4A5A7A",
          amber: "#C8A24A",
          // Signal colors
          urgent: "#FF4444",
          warn: "#FF9900",
          ok: "#44BB44",
          intel: "#4488FF",
        },
      },
      fontFamily: {
        serif: ["EB Garamond", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      backgroundImage: {
        "rr-gradient": "linear-gradient(135deg, #0A0A0A 0%, #141414 50%, #0A0A0A 100%)",
      },
      animation: {
        "pulse-brass": "pulse-brass 2s ease-in-out infinite",
        "slide-in": "slide-in 0.2s ease-out",
      },
      keyframes: {
        "pulse-brass": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
