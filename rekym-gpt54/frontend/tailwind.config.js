/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#E5F1FF",
          100: "#D2E5FF",
          300: "#69A6FC",
          500: "#007CFF",
          600: "#005CE5",
          700: "#0A2FB2",
        },
        navy: {
          50: "#F6F9FD",
          100: "#EEF2F9",
          200: "#E0E8F3",
          600: "#6780A9",
          700: "#445C85",
          900: "#0A2757",
        },
        surface: {
          DEFAULT: "#F6F9FD",
          alt: "#EEF2F9",
        },
        success: {
          100: "#CAF2E0",
          600: "#12AF80",
        },
        warning: {
          100: "#FAE3C2",
          600: "#C67D10",
        },
        danger: {
          100: "#F4C7C9",
          600: "#B50707",
        },
      },
      fontFamily: {
        sans: ['"Proxima Soft"', "Inter", "Segoe UI", "sans-serif"],
        display: ["Gilroy", '"Proxima Soft"', "Inter", "sans-serif"],
        mono: ['"Fira Code"', "monospace"],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0, 0, 0, 0.08)",
      },
      borderRadius: {
        card: "0.75rem",
      },
    },
  },
  plugins: [],
};