/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, Vite forwards API and back-office calls to Django so the browser sees one
// origin, exactly as it does in production behind Nginx. changeOrigin stays false so Django
// sees the browser's Host header and its CSRF origin check matches, like behind Nginx.
const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const toDjango = { target: backend, changeOrigin: false }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': toDjango,
      '/backoffice': toDjango,
      '/static': toDjango,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
    testTimeout: 15_000,
  },
})
