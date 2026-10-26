// 전체 흐름이 끝까지 도는지 확인: 진단 생성 → Mock 콜백 → COMPLETED(또는 질문 답변 → 재진단 → COMPLETED)
//   k6 run -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/smoke.js
// 질문 경로까지 보려면 Mock의 MOCK_QUESTION_RATIO를 높여 둔다.
import { check } from 'k6';
import { baseThresholds } from '../lib/config.js';
import { createDiagnoses, listProducts } from '../lib/api.js';
import { browseJourney, followDiagnosis } from '../lib/flows.js';
import { diagnosesBody } from '../lib/payloads.js';

export const options = {
  scenarios: {
    smoke: { executor: 'per-vu-iterations', vus: 2, iterations: 2, maxDuration: '15m' },
  },
  thresholds: {
    ...baseThresholds,
    checks: ['rate==1'],
    http_req_failed: ['rate==0'],
  },
};

export default function () {
  const user = __VU; // VU마다 다른 유저
  check(listProducts(user), { '목록 응답에 products가 있음': (d) => d && Array.isArray(d.products) });

  const created = createDiagnoses(user, diagnosesBody(2));
  check(created, { '진단 생성 응답에 diagnosesId가 있음': (d) => d && d.diagnosesId });
  if (!created) {
    return;
  }

  const detail = followDiagnosis(user, created.diagnosesId);
  check(detail, {
    '모든 상품이 COMPLETED': (d) => d && d.products.every((p) => p.processingStatus === 'COMPLETED'),
    '결과 카드가 저장됨': (d) => d && d.products.every((p) => p.toolReviews.length > 0),
    '진행 단계가 기록됨': (d) => d && d.products.every((p) => p.progresses.length > 0),
  });

  browseJourney(user);
}
