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
    // 화면을 렌더하고 사용자 조작을 이어 가는 통합 테스트는 부하가 걸리면 기본 5초를 넘길 수 있다. (asyncUtilTimeout=5초보다 길어야 한다)
    testTimeout: 15000,
    // 개발 환경(.env)과 상관없이 API 주소를 고정한다. 빈 값이면 jsdom 주소와 같은 출처(상대 경로)로 요청한다.
    // 다른 출처로 두면 jsdom XHR이 CORS 응답 헤더 없는 모킹 응답을 네트워크 오류로 처리하기 때문이다. (MSW 핸들러도 이 값을 쓴다)
    env: { VITE_API_URL: '' },
    environment: 'jsdom',
    setupFiles: ['./src/test/vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // 커버리지는 `npm run test:coverage`로 측정하고, CI는 아래 기준에 못 미치면 실패한다.
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      // 테스트 코드와 테스트 보조 파일, BE 없이 화면을 볼 때만 쓰는 목업, 타입 선언, 앱 시작 코드(main, Sentry 초기화)는 측정하지 않는다.
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/api/mock/**', 'src/**/*.d.ts', 'src/main.tsx', 'src/instrument.ts'],
      thresholds: { statements: 70, branches: 70, functions: 70, lines: 70 },
    },
  },
})
