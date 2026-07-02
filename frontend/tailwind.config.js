/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // JobLogic brand palette (from prototype)
        jl: {
          teal: '#0eb6bd',
          'teal-dark': '#0b6e74',
          navy: '#0d3443',
          'navy-dark': '#0a2935',
          green: '#27ae60',
          'green-dark': '#1f9150',
          orange: '#d97706',
        },
        rag: {
          red: '#e8534a',
          'red-bg': '#fdeceb',
          amber: '#f2994a',
          'amber-bg': '#fdf3e8',
          green: '#27ae60',
          'green-bg': '#e9f7ef',
          grey: '#94a3b8',
          'grey-bg': '#eef1f3',
          // AMP warning banner — deep amber on a pale cream wash (matches design spec)
          warn: '#d97706',
          'warn-bg': '#fef6e7',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
