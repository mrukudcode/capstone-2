import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,

    proxy: {
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },

      '/policies': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },

      '/claims': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },

      '/documents': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },

      '/rules': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },

      // IMPORTANT:
      // Proxy ICD-10 API requests to FastAPI
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})