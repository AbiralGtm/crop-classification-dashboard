import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        crop: {
          green: "#1a9850",
          amber: "#fee08b",
        },
      },
    },
  },
  plugins: [],
};
export default config;
