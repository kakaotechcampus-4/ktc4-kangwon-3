import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { MAX_WAIT_MS } from './config.js';
import { answerQuestions, createDiagnoses, getDiagnoses, getProduct, listProducts } from './api.js';
import { diagnosesBody, keyword } from './payloads.js';

// 생성 → 폴링 종료(pollIntervalMs == null이고 답할 질문 없음)까지. asked 태그로 질문이 있었던 진단을 나눈다.
export const diagnosisE2E = new Trend('diagnosis_e2e_duration', true);
export const pollCount = new Trend('diagnosis_poll_count');
export const productOutcome = new Counter('diagnosis_product_outcome');
export const diagnosisTimeout = new Counter('diagnosis_timeout');

function think(min = 1, max = 3) {
  sleep(min + Math.random() * (max - min));
}

// FE와 같이 진단을 끝까지 따라간다. pollIntervalMs 간격으로 폴링하고, 답변 대기 상품이 있으면 답한다.
export function followDiagnosis(user, diagnosesId) {
  const startedAt = Date.now();
  const answered = new Set();
  let polls = 0;
  let asked = false;
  let detail = null;

  while (Date.now() - startedAt < MAX_WAIT_MS) {
    detail = getDiagnoses(user, diagnosesId);
    polls++;
    if (!detail) {
      sleep(3);
      continue;
    }

    let answeredNow = false;
    for (const product of detail.products) {
      if (product.processingStatus !== 'AWAITING_INPUT') {
        continue;
      }
      const pending = product.questions.filter((q) => q.answerText === null && !answered.has(q.questionId));
      if (pending.length === 0) {
        continue;
      }
      asked = true;
      think(2, 5); // 질문을 읽고 답하는 시간
      const answers = pending.map((q) => ({ questionId: q.questionId, answerText: '네, 해당합니다.' }));
      if (answerQuestions(user, product.productId, answers)) {
        pending.forEach((q) => answered.add(q.questionId));
        answeredNow = true;
      }
    }

    if (detail.pollIntervalMs === null && !answeredNow) {
      break;
    }
    sleep((detail.pollIntervalMs || 3000) / 1000);
  }

  const done = detail !== null && detail.pollIntervalMs === null;
  if (!done) {
    diagnosisTimeout.add(1);
  }
  check(done, { '진단이 제한 시간 안에 끝남': (d) => d });
  diagnosisE2E.add(Date.now() - startedAt, { asked: String(asked) });
  pollCount.add(polls);
  if (detail) {
    detail.products.forEach((p) => productOutcome.add(1, { status: p.processingStatus }));
  }
  return detail;
}

// 진단하는 사용자: 목록 → 진단 생성 → 폴링(질문 답변) → 결과 상세 → 목록
export function diagnosisJourney(user) {
  listProducts(user);
  think();
  const created = createDiagnoses(user, diagnosesBody());
  if (!created) {
    return;
  }
  const detail = followDiagnosis(user, created.diagnosesId);
  if (detail && detail.products.length > 0) {
    think();
    getProduct(user, detail.products[0].productId);
  }
  think();
  listProducts(user);
}

// 둘러보기만 하는 사용자: 목록(가끔 검색) → 상세 몇 개
export function browseJourney(user) {
  const list = Math.random() < 0.3 ? listProducts(user, { keyword: keyword() }) : listProducts(user);
  const products = (list && list.products) || [];
  const count = Math.min(products.length, 1 + Math.floor(Math.random() * 3));
  for (let i = 0; i < count; i++) {
    think();
    getProduct(user, products[i].productId);
  }
}
