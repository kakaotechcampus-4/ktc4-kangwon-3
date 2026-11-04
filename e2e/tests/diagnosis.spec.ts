import { type Page } from "@playwright/test";

import { expect, test } from "../fixtures/auth";

// 진단은 mock-ai 기준 상품마다 몇 초가 걸린다. 결과가 나올 때까지 기다리는 상한.
const DIAGNOSIS_TIMEOUT = 30_000;

async function addTextProduct(page: Page, productName: string, content: string) {
    await page.getByRole("button", { name: "텍스트 / 이미지" }).click();
    await page.getByLabel("제품명").fill(productName);
    await page.getByLabel("제품 상세페이지 내용").fill(content);
    await page.getByRole("button", { name: "상품 추가하기" }).click();
}

async function addUrlProduct(page: Page, productName: string, url: string) {
    await page.getByRole("button", { name: "URL", exact: true }).click();
    await page.getByLabel("제품명").fill(productName);
    await page.getByLabel("제품 상세페이지 링크").fill(url);
    await page.getByRole("button", { name: "상품 추가하기" }).click();
}

test("텍스트로 진단을 요청하면 진행 화면을 거쳐 결과 화면에서 판정을 확인할 수 있다", async ({ page }) => {
    // given
    await page.goto("/upload");
    await addTextProduct(page, "E2E 블루투스 이어폰", "[e2e:certification] 블루투스 5.3 무선 이어폰, 충전 케이스 포함");

    // when
    await page.getByRole("button", { name: "진단 시작하기" }).click();

    // then: 진행 화면으로 이동하고, 진단이 끝나면 결과로 넘어갈 수 있다.
    await expect(page).toHaveURL(/\/judgement\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: "상품을 진단하고 있어요" })).toBeVisible();
    await page.getByRole("link", { name: "결과 보기" }).click({ timeout: DIAGNOSIS_TIMEOUT });

    await expect(page).toHaveURL(/\/result\/product\/[0-9a-f-]{36}$/);
    await expect(page.getByText("사입 인증 필요 · 해야 할 일 1건")).toBeVisible();
});

test("URL로 진단을 요청해도 결과 화면에서 판정을 확인할 수 있다", async ({ page }) => {
    // given
    await page.goto("/upload");
    await addUrlProduct(page, "E2E 캠핑 테이블", "https://www.aliexpress.com/item/1005006000000001.html?e2e=allowed");

    // when
    await page.getByRole("button", { name: "진단 시작하기" }).click();
    await page.getByRole("link", { name: "결과 보기" }).click({ timeout: DIAGNOSIS_TIMEOUT });

    // then
    await expect(page).toHaveURL(/\/result\/product\/[0-9a-f-]{36}$/);
    await expect(page.getByText("구매 대행 가능").first()).toBeVisible();
});
