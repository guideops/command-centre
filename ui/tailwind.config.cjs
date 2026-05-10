/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0f',
        surface: '#12121a',
        'surface-2': '#1a1a27',
        border: '#2a2a3d',
        'border-glow': '#3d3d5c',
        text: '#e8e8f0',
        'text-dim': '#8888a0',
        'text-subtle': '#5a5a70',
        accent: '#4d7cff',
        'accent-2': '#8b5cf6',
        green: '#10b981',
        amber: '#f59e0b',
        red: '#ef4444',
        cyan: '#06b6d4',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      backgroundImage: {
        'accent-gradient': 'linear-gradient(135deg, #4d7cff, #8b5cf6)',
      },
      borderRadius: {
        DEFAULT: '0.75rem',
        lg: '1rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
