/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// One origin: the browser talks only to Vite, which proxies /api.
//   npm run dev       → Django backend on 127.0.0.1:8000 (docker compose up)
//   npm run dev:mock  → Prism mock on 127.0.0.1:4010 (docker compose --profile mock up -d mock)
export default defineConfig(({ mode }) => {
  const useMock = mode === "mock";
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": path.resolve(import.meta.dirname, "src") },
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": {
          target: useMock ? "http://127.0.0.1:4010" : "http://127.0.0.1:8000",
          // Keep the browser Host header so Django's CSRF origin check sees one origin.
          changeOrigin: false,
          // Prism enforces the contract's session cookie; give it a fake one.
          headers: useMock ? { cookie: "sessionid=mock" } : undefined,
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
