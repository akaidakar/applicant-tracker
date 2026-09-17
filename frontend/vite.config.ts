import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy the API and the Django admin (for the session login) so the browser
// sees one origin: no CORS, and the session cookie works for /api.
const django = { target: 'http://localhost:8000', changeOrigin: true }

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': django,
      '/admin': django,
      // The submission tester page posts here.
      '/submission': django,
      // The admin login page loads its CSS from here.
      '/static': django,
    },
  },
})
