import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Temporary: during Sprint 1-3 we ship the React app under `/beta/`
  // while Django keeps serving the old HTML at `/`. Sprint 4's Caddy
  // flip moves React to `/` and this base becomes `/`.
  base: '/beta/',
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
