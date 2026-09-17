import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy the API and the Django admin (for the session login) so the browser
// sees one origin: no CORS, and the session cookie works for /api.
const django = { target: 'http://localhost:8000', changeOrigin: true }

export default defineConfig({
  // GitHub Pages serves the demo from /<repo>/, so the build sets VITE_BASE.
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': django,
      '/admin': django,
      // The admin login page loads its CSS from here.
      '/static': django,
    },
  },
})
