import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // 유닛·통합 테스트. 외부 API는 모킹하고 프론트엔드 내부 로직과 화면 동작만 검증한다.
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
