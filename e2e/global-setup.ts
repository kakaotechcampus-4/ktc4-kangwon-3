import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

// BE·DB·Redis·mock-ai를 띄우고 테스트 사용자를 넣는다.
// 스택을 직접 띄워 둔 채 반복 실행할 때는 E2E_KEEP_STACK=1로 건너뛴다.
const COMPOSE = "docker compose -f compose.e2e.yml";

export default function globalSetup() {
    if (process.env.E2E_KEEP_STACK === "1") {
        return;
    }
    execSync(`${COMPOSE} up -d --build --wait`, { stdio: "inherit" });
    execSync(`${COMPOSE} exec -T db psql -U e2e -d beforeselling`, {
        input: readFileSync("seed/users.sql"),
        stdio: ["pipe", "inherit", "inherit"],
    });
}
