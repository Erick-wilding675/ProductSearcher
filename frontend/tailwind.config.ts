import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "24px", screens: { "2xl": "1280px" } },
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-alt": "var(--surface-alt)",
        border: "var(--border)",
        text: "var(--text)",
        "text-muted": "var(--text-muted)",
        primary: {
          DEFAULT: "var(--primary)", hover: "var(--primary-hover)",
          on: "var(--primary-on)", foreground: "var(--primary-on)",
        },
        "accent-surface": "var(--accent-surface)",
        offer: "#EC4899",
        violet: {
          50: "#F5F3FF", 100: "#EDE9FE", 200: "#DDD6FE", 300: "#C4B5FD",
          400: "#A78BFA", 500: "#8B5CF6", 600: "#7C3AED", 700: "#6D28D9",
          800: "#5B21B6", 900: "#4C1D95",
        },
        success: "#16A34A", warning: "#F59E0B", error: "#DC2626", info: "#2563EB",
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
      fontSize: {
        display: ["32px", { lineHeight: "40px", fontWeight: "700" }],
        h1: ["28px", { lineHeight: "36px", fontWeight: "700" }],
        h2: ["22px", { lineHeight: "30px", fontWeight: "600" }],
        h3: ["18px", { lineHeight: "26px", fontWeight: "600" }],
        "body-l": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        body: ["14px", { lineHeight: "20px", fontWeight: "400" }],
        small: ["12px", { lineHeight: "16px", fontWeight: "500" }],
        caption: ["11px", { lineHeight: "14px", fontWeight: "500" }],
      },
      boxShadow: {
        sm: "0 1px 2px rgba(15, 23, 42, 0.06)",
        md: "0 4px 12px rgba(15, 23, 42, 0.08)",
        lg: "0 12px 32px rgba(15, 23, 42, 0.16)",
      },
      borderRadius: { sm: "6px", md: "8px", lg: "12px", xl: "16px" },
      fontFamily: { sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;