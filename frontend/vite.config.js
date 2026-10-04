import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The glossary lives in ../data (single source of truth shared with the backend).
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
})
