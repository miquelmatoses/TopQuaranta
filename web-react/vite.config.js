import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Sprint 4: React is the primary UI served from the site root. The
  // Django app still runs behind Caddy for `/api/*`, 2FA flows, email
  // activation and sitemap/robots. Everything else falls through to
  // the SPA index.
  base: '/',
  server: {
    // During dev (`npm run dev`), proxy API calls to the local Django
    // gunicorn so the React app talks to the real backend without CORS.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8083',
        changeOrigin: true,
      },
    },
  },
  ssr: {
    noExternal: ['mm-design'],
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
})
