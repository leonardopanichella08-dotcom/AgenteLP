/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    screens: {
      xs: '560px',
      sm: '640px',
      short: { raw: '(orientation: landscape) and (max-height: 520px)' },
    },
    extend: {
      fontFamily: {
        display: ['ui-rounded', '"Arial Rounded MT Bold"', '"Trebuchet MS"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
