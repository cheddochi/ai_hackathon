/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        accent: "#4F46E5",
        "accent-light": "#EEF2FF",
        success: "#10B981",
        danger: "#EF4444",
        warning: "#F59E0B",
        surface: "#F9FAFB",
      },
      fontFamily: {
        sans: ["Inter", "Pretendard", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};
