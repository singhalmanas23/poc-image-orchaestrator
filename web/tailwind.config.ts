import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0A0A0C",
          800: "#101013",
          700: "#16161B",
          600: "#1D1D24",
          500: "#262630",
        },
        line: {
          DEFAULT: "#2A2A33",
          soft: "rgba(237, 230, 211, 0.07)",
        },
        bone: {
          DEFAULT: "#EDE6D3",
          dim: "#9A9281",
          mute: "#5C5648",
        },
        saffron: {
          DEFAULT: "#F4A340",
          deep: "#C77E22",
          glow: "rgba(244, 163, 64, 0.16)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
        wider2: "0.18em",
        widest2: "0.32em",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
        flicker: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.85" },
        },
        rise: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        scan: "scan 2.4s linear infinite",
        pulseDot: "pulseDot 1.8s ease-in-out infinite",
        flicker: "flicker 3s ease-in-out infinite",
        rise: "rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
};

export default config;
