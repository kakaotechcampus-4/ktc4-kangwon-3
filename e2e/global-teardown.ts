import { execSync } from "node:child_process";

// 테스트가 끝나면 스택을 내리고 데이터(tmpfs)를 버린다.
export default function globalTeardown() {
    if (process.env.E2E_KEEP_STACK === "1") {
        return;
    }
    execSync("docker compose -f compose.e2e.yml down -v", { stdio: "inherit" });
}
