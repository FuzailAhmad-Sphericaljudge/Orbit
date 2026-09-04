import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["festive-dandelion-colonize.ngrok-free.dev"],
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          return id.includes("/node_modules/three/") ? "three" : undefined;
        },
      },
    },
  },
});
