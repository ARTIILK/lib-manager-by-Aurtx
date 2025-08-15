/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      colors: {
        tealLight: "#EDF7F6",
        blueGray: "#2E4756",
        blueGrayHover: "#3A5A6B",
      }
    },
  },
  plugins: [],
}