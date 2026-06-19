import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // NeuroGuard brand palette
        brand: {
          50:  "#f0f4ff",
          100: "#e0eaff",
          200: "#c7d7fe",
          300: "#a5bbfc",
          400: "#8098f9",
          500: "#6172f3",  // primary
          600: "#4e55e8",
          700: "#4042d4",
          800: "#3738ab",
          900: "#313787",
          950: "#1e1f51",
        },
        // Risk tier colours (matches risk.ts utility)
        risk: {
          "very-low":  "#22c55e",   // green-500
          low:         "#84cc16",   // lime-500
          moderate:    "#f59e0b",   // amber-500
          high:        "#f97316",   // orange-500
          "very-high": "#ef4444",   // red-500
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "pulse-slow": {
          "0%, 100%": { opacity: "1" },
          "50%":       { opacity: "0.5" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateY(-8px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-slow": "pulse-slow 3s ease-in-out infinite",
        "slide-in":   "slide-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
