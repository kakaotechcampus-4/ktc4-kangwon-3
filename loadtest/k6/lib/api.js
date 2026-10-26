import http from 'k6/http';
import { check } from 'k6';
import { BASE_URL } from './config.js';
import { tokenOf } from './auth.js';

// 요청마다 name 태그를 붙여 path 변수(diagnosesId 등)로 지표가 쪼개지지 않게 한다.
function params(user, name) {
  return {
    headers: { Authorization: `Bearer ${tokenOf(user)}`, 'Content-Type': 'application/json' },
    tags: { name },
  };
}

function data(res) {
  try {
    return res.json('data');
  } catch (e) {
    return null;
  }
}

function ok(res, name) {
  return check(res, { [`${name} 200`]: (r) => r.status === 200 });
}

export function listProducts(user, query = {}) {
  const name = query.keyword ? 'GET /products?keyword' : 'GET /products';
  const qs = Object.entries({ page: 0, size: 10, sortType: 'LATEST', ...query })
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&');
  const res = http.get(`${BASE_URL}/api/v1/products?${qs}`, params(user, name));
  ok(res, name);
  return data(res);
}

export function getProduct(user, productId) {
  const name = 'GET /products/{id}';
  const res = http.get(`${BASE_URL}/api/v1/products/${productId}`, params(user, name));
  ok(res, name);
  return data(res);
}

export function createDiagnoses(user, body) {
  const name = 'POST /diagnoses';
  const res = http.post(`${BASE_URL}/api/v1/diagnoses`, JSON.stringify(body), params(user, name));
  ok(res, name);
  return data(res);
}

export function getDiagnoses(user, diagnosesId) {
  const name = 'GET /diagnoses/{id}';
  const res = http.get(`${BASE_URL}/api/v1/diagnoses/${diagnosesId}`, params(user, name));
  ok(res, name);
  return data(res);
}

export function answerQuestions(user, productId, answers) {
  const name = 'POST /products/{id}/answers';
  const res = http.post(`${BASE_URL}/api/v1/products/${productId}/answers`, JSON.stringify({ answers }),
    params(user, name));
  return ok(res, name);
}
