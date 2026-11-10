import { expect, test } from "../fixtures/auth";
import { DIAGNOSIS_TIMEOUT, startTextDiagnosis } from "../helpers/upload";

test("진단한 상품은 진단 결과 목록에 나오고, 누르면 그 상품의 결과로 이동한다", async ({ page }) => {
    // given: 다른 테스트의 상품과 구분되는 이름으로 진단을 끝낸다.
    const productName = `E2E 진단 결과 상품 ${Date.now()}`;
    await startTextDiagnosis(page, productName, "[e2e:certification] 마이페이지 확인용 상품");
    await expect(page.getByRole("link", { name: "결과 보기" })).toBeVisible({ timeout: DIAGNOSIS_TIMEOUT });

    // when
    await page.goto("/");
    await page.getByRole("link", { name: "진단 결과", exact: true }).click();
    await expect(page).toHaveURL(/\/products$/);
    await page.getByRole("heading", { name: productName }).click();

    // then
    await expect(page).toHaveURL(/\/result\/product\/[0-9a-f-]{36}$/);
    await expect(page.getByText("사입 인증 필요 · 해야 할 일 1건")).toBeVisible();
});
