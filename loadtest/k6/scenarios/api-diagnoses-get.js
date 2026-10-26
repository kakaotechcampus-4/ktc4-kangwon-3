// 단일 API 기준선: 진단 상세(폴링 대상). 상품·진행·질문·결과 카드까지 읽어 요청당 약 10쿼리.
//   k6 run -e STEPS=10,25,50,100,200 -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/api-diagnoses-get.js
// setup에서 prepare.js가 만든 진단 ID를 목록 API로 모은다.
import { baseThresholds, READ_P95_MS } from '../lib/config.js';
import { getDiagnoses, listProducts } from '../lib/api.js';
import { rpsSteps } from '../config/profiles.js';

const USERS = Number(__ENV.PREPARE_USERS || 200);

export const options = {
  scenarios: { diagnoses_get: rpsSteps('10,25,50,100,200') },
  thresholds: {
    ...baseThresholds,
    'http_req_duration{name:GET /diagnoses/{id}}': [`p(95)<${READ_P95_MS}`],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
  setupTimeout: '5m',
};

export function setup() {
  const targets = [];
  for (let user = 1; user <= USERS; user++) {
    const list = listProducts(user, { size: 20 });
    const ids = new Set(((list && list.products) || []).map((p) => p.diagnosesId));
    ids.forEach((diagnosesId) => targets.push({ user, diagnosesId }));
  }
  if (targets.length === 0) {
    throw new Error('조회할 진단이 없습니다. prepare.js를 먼저 실행하세요.');
  }
  return { targets };
}

export default function ({ targets }) {
  const { user, diagnosesId } = targets[Math.floor(Math.random() * targets.length)];
  getDiagnoses(user, diagnosesId);
}
