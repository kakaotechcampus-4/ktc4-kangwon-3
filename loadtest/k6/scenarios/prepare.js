// 조회 기준선(api-products-list, api-diagnoses-get)용 데이터 준비. seed.sql 다음에 한 번 실행한다.
// 앞쪽 PREPARE_USERS명에게 진단을 PREPARE_PER_USER개씩 만들어 둔다. 완료는 기다리지 않으므로
// 끝난 뒤 Mock 처리 시간(기본 최대 2분)만큼 기다렸다가 기준선을 돌린다.
//   k6 run -e BASE_URL=... -e JWT_SECRET=... k6/scenarios/prepare.js
import exec from 'k6/execution';
import { createDiagnoses } from '../lib/api.js';
import { diagnosesBody } from '../lib/payloads.js';

const USERS = Number(__ENV.PREPARE_USERS || 200);
const PER_USER = Number(__ENV.PREPARE_PER_USER || 5);

export const options = {
  scenarios: {
    prepare: {
      executor: 'shared-iterations',
      vus: 10,
      iterations: USERS * PER_USER,
      maxDuration: '20m',
    },
  },
  thresholds: { http_req_failed: ['rate<0.01'] },
};

export default function () {
  // 전체 반복 번호로 유저를 고르게 나눈다(1..USERS). __ITER는 VU별 번호라 쓰지 않는다.
  const user = (exec.scenario.iterationInTest % USERS) + 1;
  createDiagnoses(user, diagnosesBody());
}
