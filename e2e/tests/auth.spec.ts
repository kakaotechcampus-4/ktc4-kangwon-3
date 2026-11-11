import { expect, test as guestTest } from "@playwright/test";

import { test } from "../fixtures/auth";

test("로그인 상태로 시작하면 로그인이 필요한 마이페이지에 들어갈 수 있다", async ({ page }) => {
    // when
    await page.goto("/mypage");

    // then
    await expect(page).toHaveURL(/\/mypage$/);
    await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();
});

guestTest("로그인하지 않으면 마이페이지에서 로그인 화면으로 이동한다", async ({ page }) => {
    // when
    await page.goto("/mypage");

    // then
    await expect(page).toHaveURL(/\/login$/);
});
