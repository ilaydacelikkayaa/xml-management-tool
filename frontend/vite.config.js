
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/collections': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
      '/projects': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
      '/global-lists': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
    },
  },
})
