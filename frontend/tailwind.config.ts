import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

// Tokens do design system (ver docs/design-system.md). Hero: violet.
// Os nomes que o shadcn/ui espera (background, foreground, ring, muted, accent...)
// apontam para os NOSSOS tokens -> uma única fonte de verdade.
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // --- nossos tokens ---
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
          foreground: "var(--primary-on)",
        },
        "accent-surface": "var(--accent-surface)",
        violet: {
          50: "#F5F3FF", 100: "#EDE9FE", 200: "#DDD6FE", 300: "#C4B5FD",
          400: "#A78BFA", 500: "#8B5CF6", 600: "#7C3AED", 700: "#6D28D9",
          800: "#5B21B6", 900: "#4C1D95",
        },
        success: "#16A34A",
        warning: "#F59E0B",
        error: "#DC2626",
        info: "#2563EB",
        // --- de-para p/ shadcn/ui (aponta para os nossos tokens) ---
        background: "var(--bg)",
        foreground: "var(--text)",
        card: { DEFAULT: "var(--surface)", foreground: "var(--text)" },
        popover: { DEFAULT: "var(--surface)", foreground: "var(--text)" },
        secondary: { DEFAULT: "var(--surface-alt)", foreground: "var(--text)" },
        muted: { DEFAULT: "var(--surface-alt)", foreground: "var(--text-muted)" },
        accent: { DEFAULT: "var(--accent-surface)", foreground: "var(--primary)" },
        destructive: { DEFAULT: "#DC2626", foreground: "#FFFFFF" },
        input: "var(--border)",
        ring: "var(--focus-ring)",
      },
      borderRadius: { sm: "6px", md: "8px", lg: "12px", xl: "16px" },
      fontFamily: { sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;