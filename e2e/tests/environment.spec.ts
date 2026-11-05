import { expect, test } from "@playwright/test";

import { BE_URL } from "../playwright.config";

// 시나리오를 돌리기 전에 FE·BE가 떠 있는지 확인한다.
test("메인 화면이 열린다", async ({ page }) => {
    // when
    await page.goto("/");

    // then
    await expect(page.getByRole("heading", { name: "이 물건, 팔아도 되나요?" })).toBeVisible();
});

test("BE가 인증이 필요한 API에 401을 응답한다", async ({ request }) => {
    // when
    const response = await request.get(`${BE_URL}/api/v1/products`);

    // then
    expect(response.status()).toBe(401);
    expect((await response.json()).code).toBe("COMMON-004");
});
