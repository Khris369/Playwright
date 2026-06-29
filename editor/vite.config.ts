import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/editor/',
  plugins: [react()],
  build: { outDir: '../app/web/editor-dist', emptyOutDir: true },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.ts' },
})
