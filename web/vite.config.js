import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// v2 前端: 构建产物由 webui.py 同源托管在 /v2, 开发时 proxy 到 Flask.
export default defineConfig({
  plugins: [preact()],
  base: "/v2/",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/static": "http://127.0.0.1:8765"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
