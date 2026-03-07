/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /*
         * GCash Official Brand Palette
         * Source: gcash.com Webflow design system (2026)
         * --gcash-website-library---color-brand--*
         */

        // Primary blue — GCash brand blue (#007CFF)
        primary: {
          50:  '#E5F1FF',   // blue-pale
          100: '#D2E5FF',   // blue-lightest
          200: '#9BC5FD',   // blue-lighter
          300: '#69A6FC',   // blue-light
          400: '#1972F9',   // blue-mid
          500: '#007CFF',   // gcash-b300 — hero brand blue
          600: '#005CE5',   // blue (default interactive)
          700: '#0A2FB2',   // blue-dark
          800: '#072592',   // blue-darker
          900: '#071969',   // blue-darkest
          950: '#060F4C',   // blue-deep
        },

        // Navy — GCash deep text & heading color
        navy: {
          50:  '#F6F9FD',   // neutral-lightest
          100: '#EEF2F9',   // neutral-lighter
          200: '#E0E8F3',   // slate-pale
          300: '#D7E0EF',   // slate-lightest
          400: '#ADBDDC',   // slate-light
          500: '#7E96BE',   // slate
          600: '#6780A9',   // slate-dark
          700: '#445C85',   // slate-darker
          800: '#183462',   // slate-darkest
          900: '#0A2757',   // slate-deep — primary text
          950: '#04142D',   // gcash-b600
        },

        // Metal blue — charts & secondary accents
        metal: {
          light:   '#D6EAF5',
          DEFAULT: '#447CD0',
          dark:    '#2C5AB9',
        },

        // Dashboard stat card palette (GCash semantic)
        stat: {
          blue:    { light: '#E5F1FF', DEFAULT: '#005CE5', dark: '#0A2FB2' },
          teal:    { light: '#E9FBFB', DEFAULT: '#10BCB4', dark: '#179B95' },
          violet:  { light: '#EFE7FD', DEFAULT: '#660CED', dark: '#500ABA' },
          emerald: { light: '#E7F8F0', DEFAULT: '#27C990', dark: '#12AF80' },
        },

        // Page & card surfaces (GCash neutral scale)
        surface: {
          DEFAULT: '#F6F9FD',  // neutral-lightest
          alt:     '#EEF2F9',  // neutral-lighter
        },

        // GCash semantic palette — teal
        teal: {
          pale:    '#E9FBFB',
          light:   '#90EEEA',
          DEFAULT: '#10BCB4',
          dark:    '#179B95',
          deep:    '#184945',
        },

        // GCash semantic palette — mango / amber
        mango: {
          pale:    '#FEF5E7',
          light:   '#FAC370',
          DEFAULT: '#F9A60B',
          dark:    '#C67D10',
          deep:    '#462E0B',
        },

        // Confidence level colors
        confidence: {
          high:   '#27C990',   // GCash green
          medium: '#F9A60B',   // GCash mango
          low:    '#D61B2C',   // GCash red
        },

        // Severity colors
        severity: {
          high:   '#D61B2C',   // GCash red
          medium: '#FF6B00',   // GCash orange
          low:    '#27C990',   // GCash green
        },

        // GCash cream (warm accent)
        cream: '#FCF6EB',
      },

      fontFamily: {
        // GCash uses Proxima Soft for body, Gilroy for display
        sans:    ['"Proxima Soft"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Gilroy', '"Proxima Soft"', 'Inter', 'system-ui', 'sans-serif'],
        mono:    ['"Fira Code"', 'monospace'],
      },

      fontSize: {
        // GCash type scale (maps to --gcash-website-library---font--size-*)
        'gcash-caption':    ['0.625rem',  { lineHeight: '0.875rem' }],   // 10px
        'gcash-small':      ['0.75rem',   { lineHeight: '1.05rem' }],    // 12px
        'gcash-subcontent': ['0.875rem',  { lineHeight: '1.25rem' }],    // 14px
        'gcash-content':    ['1rem',      { lineHeight: '1.4rem' }],     // 16px
        'gcash-large':      ['1.125rem',  { lineHeight: '1.4625rem' }],  // 18px
        'gcash-h6':         ['1.25rem',   { lineHeight: '1.5625rem' }],  // 20px
        'gcash-h5':         ['1.375rem',  { lineHeight: '1.65rem' }],    // 22px
        'gcash-h4':         ['1.625rem',  { lineHeight: '1.95rem' }],    // 26px
        'gcash-h3':         ['1.875rem',  { lineHeight: '2.1rem' }],     // 30px
        'gcash-h2':         ['2.25rem',   { lineHeight: '2.475rem' }],   // 36px
        'gcash-h1':         ['3.25rem',   { lineHeight: '3.575rem' }],   // 52px
      },

      letterSpacing: {
        'gcash-h1':  '-0.03em',
        'gcash-h2':  '-0.02em',
        'gcash-h3':  '-0.02em',
        'gcash-h4':  '-0.0015em',
        'gcash-h5':  '-0.003em',
      },

      boxShadow: {
        'card':     '0 2px 8px rgba(0, 0, 0, 0.08)',
        'card-md':  '0 0 20px rgba(0, 0, 0, 0.07)',
        'elevated': '0 0 26px rgba(24, 48, 108, 0.2)',
      },

      borderRadius: {
        'card': '0.75rem',
      },

      spacing: {
        // GCash spacing scale extensions
        '18': '4.5rem',
        '22': '5.5rem',
      },

      keyframes: {
        'slide-in-right': {
          from: { transform: 'translateX(100%)' },
          to:   { transform: 'translateX(0)' },
        },
      },
      animation: {
        'slide-in-right': 'slide-in-right 0.2s ease-out',
      },
    },
  },
  plugins: [],
};
