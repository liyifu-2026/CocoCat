import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: '/app/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    target: 'esnext',
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router')) return 'vendor-react'
          if (id.includes('node_modules/@tanstack/react-query')) return 'vendor-query'
          if (id.includes('node_modules/lucide-react') || id.includes('node_modules/radix-ui') || id.includes('node_modules/sonner') || id.includes('node_modules/cmdk')) return 'vendor-ui'
          if (id.includes('node_modules/react-markdown') || id.includes('node_modules/remark-gfm')) return 'vendor-markdown'
          if (id.includes('node_modules/mermaid')) return 'vendor-mermaid'
        },
      },
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: ['www.leaif.com', 'leaif.com', '.leaif.com'],
    hmr: {
      host: 'www.leaif.com',
      protocol: 'wss',
      clientPort: 443,
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
