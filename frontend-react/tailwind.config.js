/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg:      "#0A0E1A",
        surface: "#111827",
        card:    "#141E2E",
        border:  "#1E2D40",
        cyan:    "#00D4FF",
        amber:   "#F0B429",
        emerald: "#22C55E",
        scarlet: "#EF4444",
        violet:  "#A855F7",
        muted:   "#64748B",
        text:    "#E2E8F0",
      },
      fontFamily: {
        display: ["'Bebas Neue'", "sans-serif"],
        body:    ["'Inter'", "sans-serif"],
      },
      animation: {
        "fade-in":     "fadeIn 0.35s ease-out",
        "slide-up":    "slideUp 0.35s ease-out",
        "slide-in":    "slideIn 0.3s ease-out",
        "pulse-slow":  "pulse 3s infinite",
        "bounce-soft": "bounceSoft 0.6s ease-out",
        "glow":        "glow 2s ease-in-out infinite alternate",
        "count-up":    "fadeIn 0.5s ease-out",
      },
      keyframes: {
        fadeIn:     { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideUp:    { from: { opacity: "0", transform: "translateY(16px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideIn:    { from: { opacity: "0", transform: "translateX(-16px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        bounceSoft: { "0%": { transform: "scale(0.95)" }, "60%": { transform: "scale(1.02)" }, "100%": { transform: "scale(1)" } },
        glow:       { from: { boxShadow: "0 0 10px #00D4FF40" }, to: { boxShadow: "0 0 30px #00D4FF80" } },
      },
      backgroundImage: {
        "gradient-field":  "linear-gradient(135deg, #0A0E1A 0%, #0F1B2D 100%)",
        "gradient-card":   "linear-gradient(145deg, #141E2E, #0F1B2D)",
        "gradient-accent": "linear-gradient(90deg, #00D4FF, #0099CC)",
        "gradient-gold":   "linear-gradient(90deg, #F0B429, #E09020)",
      },
    },
  },
  plugins: [],
}

