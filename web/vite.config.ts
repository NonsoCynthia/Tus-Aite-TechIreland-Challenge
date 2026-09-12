import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The browser must see the API as same-origin: retrieval has no CORS middleware
// and Authorization is not a safelisted header, so every cross-origin call is
// blocked at preflight. In dev this proxy stands in for the orchestrator serving
// the built bundle itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true } } },
  build: { outDir: 'dist', sourcemap: false },
})
