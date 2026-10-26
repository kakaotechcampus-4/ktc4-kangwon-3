// 단일 API 기준선: 상품 목록(페이지 + count 쿼리). KEYWORD_RATIO만큼 키워드 검색(lower(name) like '%kw%')을 섞는다.
//   k6 run -e STEPS=10,25,50,100,200 -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/api-products-list.js
// prepare.js로 데이터를 만든 유저(1..PREPARE_USERS)만 대상으로 해야 빈 목록 조회가 되지 않는다.
import { baseThresholds, READ_P95_MS } from '../lib/config.js';
import { listProducts } from '../lib/api.js';
import { keyword } from '../lib/payloads.js';
import { rpsSteps } from '../config/profiles.js';

const USERS = Number(__ENV.PREPARE_USERS || 200);
const KEYWORD_RATIO = Number(__ENV.KEYWORD_RATIO || 0.3);

export const options = {
  scenarios: { products_list: rpsSteps('10,25,50,100,200') },
  thresholds: {
    ...baseThresholds,
    'http_req_duration{name:GET /products}': [`p(95)<${READ_P95_MS}`],
    'http_req_duration{name:GET /products?keyword}': [`p(95)<${READ_P95_MS}`],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const user = Math.floor(Math.random() * USERS) + 1;
  if (Math.random() < KEYWORD_RATIO) {
    listProducts(user, { keyword: keyword() });
  } else {
    listProducts(user);
  }
}
