export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        stock: 'rgb(var(--stock) / <alpha-value>)',
        'stock-deep': 'rgb(var(--stock-deep) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        'ink-soft': 'rgb(var(--ink-soft) / <alpha-value>)',
        'ink-faint': 'rgb(var(--ink-faint) / <alpha-value>)',
        rule: 'rgb(var(--rule) / <alpha-value>)',
        proof: 'rgb(var(--proof) / <alpha-value>)',
        'proof-deep': 'rgb(var(--proof-deep) / <alpha-value>)',
      },
      fontFamily: {
        press: ['Geist', 'system-ui', 'sans-serif'],
        spec: ['Geist Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
