/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primary brand blue
        primary: {
          50:  '#E5F1FF',
          100: '#D2E5FF',
          200: '#9BC5FD',
          300: '#69A6FC',
          400: '#1972F9',
          500: '#007CFF',
          600: '#005CE5',
          700: '#0A2FB2',
          800: '#072592',
          900: '#071969',
          950: '#060F4C',
        },

        // Navy — deep text & heading color
        navy: {
          50:  '#F6F9FD',
          100: '#EEF2F9',
          200: '#E0E8F3',
          300: '#D7E0EF',
          400: '#ADBDDC',
          500: '#7E96BE',
          600: '#6780A9',
          700: '#445C85',
          800: '#183462',
          900: '#0A2757',
          950: '#04142D',
        },

        // Page & card surfaces
        surface: {
          DEFAULT: '#F6F9FD',
          alt:     '#EEF2F9',
        },
      },

      fontFamily: {
        sans:    ['"Proxima Soft"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Gilroy', '"Proxima Soft"', 'Inter', 'system-ui', 'sans-serif'],
        mono:    ['"Fira Code"', 'monospace'],
      },

      boxShadow: {
        card:     '0 2px 8px rgba(0, 0, 0, 0.08)',
        elevated: '0 0 26px rgba(24, 48, 108, 0.2)',
      },

      borderRadius: {
        card: '0.75rem',
      },
    },
  },
  plugins: [],
};
