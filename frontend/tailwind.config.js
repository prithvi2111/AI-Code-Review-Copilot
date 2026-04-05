/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18212f",
        mist: "#eff4fb",
        cloud: "#f7f9fc",
        panel: "rgba(255,255,255,0.68)",
        line: "rgba(24,33,47,0.08)",
      },
      boxShadow: {
        card: "0 20px 45px rgba(23, 39, 72, 0.08)",
        glow: "0 24px 80px rgba(124, 140, 186, 0.18)",
      },
      fontFamily: {
        sans: ["SF Pro Display", "Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
