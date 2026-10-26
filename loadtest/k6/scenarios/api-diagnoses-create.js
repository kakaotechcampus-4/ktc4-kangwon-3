// 단일 API 기준선: 진단 생성. 요청 자체(INSERT + 커밋 후 @Async AI 접수)와 함께,
// 접수된 상품마다 Mock 콜백(약 15회, 매번 diagnoses 행 잠금)이 1~2분 동안 이어지는 부하가 쌓인다.
// 폴링은 하지 않으므로 콜백 경로만 따로 보는 데도 쓴다.
//   k6 run -e STEPS=1,2,5,10 -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/api-diagnoses-create.js
import { baseThresholds, WRITE_P95_MS } from '../lib/config.js';
import { randomUser } from '../lib/auth.js';
import { createDiagnoses } from '../lib/api.js';
import { diagnosesBody } from '../lib/payloads.js';
import { rpsSteps } from '../config/profiles.js';

export const options = {
  scenarios: { diagnoses_create: rpsSteps('1,2,5,10') },
  thresholds: {
    ...baseThresholds,
    'http_req_duration{name:POST /diagnoses}': [`p(95)<${WRITE_P95_MS}`],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  createDiagnoses(randomUser(), diagnosesBody());
}
