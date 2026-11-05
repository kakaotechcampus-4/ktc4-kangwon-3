import { execSync } from "node:child_process";
import { createHmac, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import { test as base } from "@playwright/test";

// 소셜 로그인(OAuth)은 자동화할 수 없어, BE가 발급하는 것과 같은 리프레시 토큰을 직접 만들어 쿠키로 넣는다.
// FE는 앱이 열릴 때 이 쿠키로 /api/v1/auth/reissue를 호출해 액세스 토큰을 받으므로, 실제 재발급 경로를 그대로 거친다.

// seed/users.sql의 테스트 사용자, compose.e2e.yml의 JWT_SECRET과 같아야 한다.
export const E2E_USER_ID = "00000000-0000-7000-8000-0000000e2e01";
const JWT_SECRET = "e2e-jwt-secret-key-must-be-at-least-32-bytes-long-0123456789";
const REFRESH_TOKEN_TTL_SECONDS = 60 * 60;
const COMPOSE_FILE = fileURLToPath(new URL("../compose.e2e.yml", import.meta.url));

const base64Url = (value: string | Buffer) => Buffer.from(value).toString("base64url");

// BE JwtProvider와 같은 HS256 리프레시 토큰(jti·sub·role·type 클레임)을 만들고, BE처럼 Redis에 jti를 저장한다.
export function issueRefreshToken(userId: string = E2E_USER_ID): string {
    const jti = randomUUID();
    const now = Math.floor(Date.now() / 1000);
    const header = base64Url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = base64Url(JSON.stringify({
        jti,
        sub: userId,
        role: "USER",
        type: "REFRESH",
        iat: now,
        exp: now + REFRESH_TOKEN_TTL_SECONDS,
    }));
    const signature = createHmac("sha256", JWT_SECRET).update(`${header}.${payload}`).digest("base64url");

    // key: refresh_token:{jti}, value: userId (RefreshTokenRepository와 같은 형식)
    execSync(
        `docker compose -f "${COMPOSE_FILE}" exec -T redis redis-cli SET refresh_token:${jti} ${userId} EX ${REFRESH_TOKEN_TTL_SECONDS}`,
        { stdio: "ignore" },
    );
    return `${header}.${payload}.${signature}`;
}

// 이 test로 만든 테스트는 로그인된 상태의 브라우저로 시작한다.
export const test = base.extend({
    context: async ({ context }, use) => {
        await context.addCookies([{
            name: "refresh_token",
            value: issueRefreshToken(),
            domain: "localhost",
            path: "/api/v1/auth",
            httpOnly: true,
            secure: false,
            sameSite: "Lax",
        }]);
        await use(context);
    },
});

export { expect } from "@playwright/test";
