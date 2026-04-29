/** @type {import('tailwindcss').Config} */
const animate = require("tailwindcss-animate")

module.exports = {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // shadcn-compatible variables
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        // Keep existing mappings for compatibility
        success: "var(--color-success)",
        error: "var(--color-error)",
        warning: "var(--color-warning)",
        "bg-light": "var(--color-bg-light)",
        "bg-dark": "var(--color-bg-dark)",
        "surface-dark": "var(--color-surface-dark)",
        "surface-2": "var(--color-surface-2)",
        "text-primary": "var(--color-text)",
        "text-secondary": "var(--color-text-secondary)",
        "accent-hover": "var(--color-accent-hover)",
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        md: "var(--radius-base)",
        sm: "0.25rem",
      },
      spacing: {
        xs: "var(--space-xs)",
        sm: "var(--space-sm)",
        md: "var(--space-md)",
        lg: "var(--space-lg)",
        xl: "var(--space-xl)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        normal: "var(--duration-normal)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "message-fade-in": {
          from: { opacity: "0", transform: "translateY(8px) scale(0.98)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "bounce-dot": {
          "0%, 80%, 100%": { transform: "scale(0)" },
          "40%": { transform: "scale(1)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
        "collapsible-open": {
          from: { height: "0", opacity: "0" },
          to: { height: "var(--radix-collapsible-content-height)", opacity: "1" },
        },
        "collapsible-closed": {
          from: { height: "var(--radix-collapsible-content-height)", opacity: "1" },
          to: { height: "0", opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "message-fade-in": "message-fade-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "bounce-dot": "bounce-dot 1.4s ease-in-out infinite both",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "collapsible-open": "collapsible-open 0.2s ease-out",
        "collapsible-closed": "collapsible-closed 0.15s ease-in",
      },
    },
  },
  plugins: [animate],
}