// 혼합 시나리오: 진단하는 사용자 + 둘러보기 사용자
//   k6 run -e PROFILE=load -e CONCURRENT=50 -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/journey.js
// PROFILE: load | stress | spike | soak (config/profiles.js)
import { baseThresholds, E2E_P95_MS, READ_P95_MS, WRITE_P95_MS } from '../lib/config.js';
import { randomUser } from '../lib/auth.js';
import { browseJourney, diagnosisJourney } from '../lib/flows.js';
import { journeyScenarios } from '../config/profiles.js';

const PROFILE = __ENV.PROFILE || 'load';
const CONCURRENT = Number(__ENV.CONCURRENT || 50);

export const options = {
  scenarios: journeyScenarios(PROFILE, CONCURRENT),
  thresholds: {
    ...baseThresholds,
    'http_req_duration{name:GET /diagnoses/{id}}': [`p(95)<${READ_P95_MS}`],
    'http_req_duration{name:GET /products}': [`p(95)<${READ_P95_MS}`],
    'http_req_duration{name:GET /products/{id}}': [`p(95)<${READ_P95_MS}`],
    'http_req_duration{name:POST /diagnoses}': [`p(95)<${WRITE_P95_MS}`],
    'diagnosis_e2e_duration{asked:false}': [`p(95)<${E2E_P95_MS}`],
    diagnosis_timeout: ['count<1'],
    // 부하 생성기(로컬 PC)가 도착률을 못 맞추면 서버 문제가 아니므로 결과를 버린다
    dropped_iterations: ['count<1'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export function diagnosis() {
  diagnosisJourney(randomUser());
}

export function browse() {
  browseJourney(randomUser());
}
