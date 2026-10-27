import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { JWT_SECRET, USERS } from './config.js';

// BE JwtProvider와 같은 HS256 AT를 직접 만든다. 필터는 서명·만료·claim(type, role)만 보고 DB를 조회하지 않는다.
// 키는 JWT_SECRET 문자열의 UTF-8 바이트(Keys.hmacShaKeyFor(secret.getBytes(UTF_8)))
const HEADER = encoding.b64encode(JSON.stringify({ alg: 'HS256', typ: 'JWT' }), 'rawurl');
const TOKEN_TTL_SECONDS = 6 * 60 * 60;

// VU마다 따로 캐시한다(VU끼리 메모리를 공유하지 않음).
const tokens = {};

// seed/seed.sql과 같은 규칙: 00000000-0000-7000-8000-{n을 12자리 16진수}
export function userIdOf(n) {
  return `00000000-0000-7000-8000-${n.toString(16).padStart(12, '0')}`;
}

export function randomUser() {
  return Math.floor(Math.random() * USERS) + 1;
}

export function tokenOf(n) {
  const cached = tokens[n];
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.exp - now > 60) {
    return cached.token;
  }
  const exp = now + TOKEN_TTL_SECONDS;
  const payload = encoding.b64encode(JSON.stringify({
    jti: uuidV4(),
    sub: userIdOf(n),
    role: 'USER',
    type: 'ACCESS',
    iat: now,
    exp,
  }), 'rawurl');
  const signature = crypto.hmac('sha256', JWT_SECRET, `${HEADER}.${payload}`, 'base64rawurl');
  const token = `${HEADER}.${payload}.${signature}`;
  tokens[n] = { token, exp };
  return token;
}

function uuidV4() {
  const hex = crypto.hexEncode(crypto.randomBytes(16));
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}
