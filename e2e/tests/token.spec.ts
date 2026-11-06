import { expect, test } from "../fixtures/auth";

const FE_ORIGIN = "http://localhost:4173";

test("API 요청 중 액세스 토큰이 만료되면 자동으로 재발급받아 원래 요청을 이어간다", async ({ page }) => {
    // given: 마이페이지 목록 첫 요청에만 BE의 '액세스 토큰 만료'(401 AUTH-001) 응답을 돌려준다.
    let expiredOnce = false;
    await page.route("**/api/v1/products?**", async (route) => {
        if (expiredOnce) {
            await route.continue();
            return;
        }
        expiredOnce = true;
        await route.fulfill({
            status: 401,
            contentType: "application/json",
            headers: { "Access-Control-Allow-Origin": FE_ORIGIN, "Access-Control-Allow-Credentials": "true" },
            body: JSON.stringify({ code: "AUTH-001", message: "액세스 토큰이 만료되었습니다.", details: null, data: null }),
        });
    });
    const reissueStatuses: number[] = [];
    page.on("response", (response) => {
        if (response.url().endsWith("/api/v1/auth/reissue")) {
            reissueStatuses.push(response.status());
        }
    });

    // when
    await page.goto("/mypage");

    // then: 로그인 화면으로 튕기지 않고 목록이 보이며, 재발급이 앱 시작 때와 만료 때 두 번 성공했다.
    await expect(page.getByRole("heading", { name: "전체 상품" })).toBeVisible();
    await expect(page).toHaveURL(/\/mypage$/);
    await expect.poll(() => reissueStatuses).toEqual([200, 200]);
    expect(expiredOnce).toBe(true);
});
