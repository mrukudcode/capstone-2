import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Backend FastAPI is expected on :5001 during dev (see README run
      // instructions). Proxy avoids CORS setup for the demo.
      '/health': 'http://127.0.0.1:5001',
      '/policies': 'http://127.0.0.1:5001',
      '/claims': 'http://127.0.0.1:5001',
      '/documents': 'http://127.0.0.1:5001',
      '/rules': 'http://127.0.0.1:5001',
    },
  },
})