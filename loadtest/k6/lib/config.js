// 실행 환경 값. k6 run -e KEY=VALUE 로 넘긴다.
export const BASE_URL = (__ENV.BASE_URL || 'http://localhost:18080').replace(/\/$/, '');
export const JWT_SECRET = __ENV.JWT_SECRET;
// seed/seed.sql로 넣은 테스트 유저 수
export const USERS = Number(__ENV.USERS || 1000);
// 진단 하나를 기다리는 최대 시간. 넘으면 실패로 센다(멈춘 진단 정리 기준 15분보다 짧게).
export const MAX_WAIT_MS = Number(__ENV.MAX_WAIT_MS || 10 * 60 * 1000);

if (!JWT_SECRET) {
  throw new Error('JWT_SECRET이 없습니다. .env.perf의 JWT_SECRET을 -e JWT_SECRET=... 으로 넘겨주세요.');
}

// SLO 초안. 로컬 PC → EC2 왕복 지연이 섞이므로 응답시간 판단은 Grafana(서버 측)를 기준으로 하고,
// 여기서는 명백히 무너졌을 때 멈추는 안전장치로 쓴다.
export const READ_P95_MS = Number(__ENV.READ_P95_MS || 500);
export const WRITE_P95_MS = Number(__ENV.WRITE_P95_MS || 1000);
// 질문 없이 끝난 진단의 생성 → 완료 시간. Mock 최대 처리 시간(120s) + 폴링 간격 등 여유
export const E2E_P95_MS = Number(__ENV.E2E_P95_MS || 130 * 1000);

export const baseThresholds = {
  // 에러율이 5%를 넘으면 1분 뒤 판단해 중단(운영 EC2 보호)
  http_req_failed: [{ threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '1m' }, 'rate<0.01'],
  checks: ['rate>0.99'],
};
