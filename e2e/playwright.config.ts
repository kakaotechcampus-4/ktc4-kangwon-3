import { defineConfig, devices } from "@playwright/test";

// FE(vite preview)와 BE 주소. BE·DB·Redis·mock-ai는 compose.e2e.yml로 띄운다.
const FE_URL = "http://localhost:4173";
export const BE_URL = "http://localhost:28080";

export default defineConfig({
    testDir: "./tests",
    // 진단은 상품마다 mock-ai 기준 몇 초가 걸려 기본(30초)보다 여유를 둔다.
    timeout: 60_000,
    expect: { timeout: 15_000 },
    // 같은 테스트 사용자를 쓰므로 순서대로 실행한다.
    workers: 1,
    fullyParallel: false,
    retries: process.env.CI ? 1 : 0,
    forbidOnly: !!process.env.CI,
    reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
    globalSetup: "./global-setup.ts",
    globalTeardown: "./global-teardown.ts",
    use: {
        baseURL: FE_URL,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
    },
    projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
    webServer: {
        // 운영과 같은 빌드 결과물을 띄운다. FE 의존성(npm ci)은 미리 설치돼 있어야 한다.
        command: "npm run build && npm run preview -- --port 4173 --strictPort",
        cwd: "../frontend/palgijeonae",
        url: FE_URL,
        env: { VITE_API_URL: BE_URL },
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
    },
});
