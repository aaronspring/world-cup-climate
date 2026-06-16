import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/world-cup-climate/", // project page: aaronspring.github.io/world-cup-climate
  plugins: [react(), tailwindcss()],
});
