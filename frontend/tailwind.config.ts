import type { Config } from "tailwindcss";

// Tokens do design system (ver docs/design-system.md). Hero: violet.
// Cores semânticas mapeadas para CSS vars (light/dark em globals.css).
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-alt": "var(--surface-alt)",
        border: "var(--border)",
        text: "var(--text)",
        "text-muted": "var(--text-muted)",
        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          on: "var(--primary-on)",
        },
        "accent-surface": "var(--accent-surface)",
        violet: {
          50: "#F5F3FF",
          100: "#EDE9FE",
          200: "#DDD6FE",
          300: "#C4B5FD",
          400: "#A78BFA",
          500: "#8B5CF6",
          600: "#7C3AED",
          700: "#6D28D9",
          800: "#5B21B6",
          900: "#4C1D95",
        },
        success: "#16A34A",
        warning: "#F59E0B",
        error: "#DC2626",
        info: "#2563EB",
      },
      borderRadius: { sm: "6px", md: "8px", lg: "12px", xl: "16px" },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};

export default config;
