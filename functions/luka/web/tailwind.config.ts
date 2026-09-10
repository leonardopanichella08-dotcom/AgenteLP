import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#FFFFFF", muted: "#F8F9FA", sunken: "#F1F3F5" },
        line: { DEFAULT: "#E2E8F0", strong: "#CBD5E1" },
        ink: { DEFAULT: "#0F172A", soft: "#475569", faint: "#94A3B8" },
        brand: { DEFAULT: "#0A66C2", hover: "#08528F", tech: "#111827" },
        ok: "#16A34A",
        warn: "#D97706",
      },
      fontFamily: {
        sans: ["Inter", "Plus Jakarta Sans", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.125rem" },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04)",
        pop: "0 8px 24px -8px rgb(15 23 42 / 0.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;
