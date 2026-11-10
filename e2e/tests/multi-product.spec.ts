import { expect, test } from "../fixtures/auth";
import { addTextProduct, DIAGNOSIS_TIMEOUT } from "../helpers/upload";

test("여러 상품을 한 번에 진단하면 상품별로 진행되고, 진단서에서 상품마다 결과를 확인할 수 있다", async ({ page }) => {
    // given: 결과가 다른 상품 두 개
    await page.goto("/upload");
    await addTextProduct(page, "E2E 무선 충전기", "[e2e:certification] 고속 무선 충전 패드");
    await addTextProduct(page, "E2E 원목 도마", "[e2e:allowed] 원목 주방 도마");

    // when
    await page.getByRole("button", { name: "진단 시작하기" }).click();

    // then: 진행 화면에 두 상품이 따로 표시되고, 각각 끝나면 결과 보기가 생긴다.
    await expect(page.getByRole("heading", { name: "E2E 무선 충전기" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "E2E 원목 도마" })).toBeVisible();
    await expect(page.getByRole("link", { name: "결과 보기" })).toHaveCount(2, { timeout: DIAGNOSIS_TIMEOUT });

    // then: 진단서에서 상품 탭을 바꿔 가며 각 상품의 판정을 확인한다.
    await page.getByRole("button", { name: "진단서 보기 →" }).click();
    await expect(page).toHaveURL(/\/result\/diagnoses\/[0-9a-f-]{36}$/);

    await page.getByRole("tab", { name: "E2E 무선 충전기" }).click();
    await expect(page.getByText("사입 인증 필요 · 해야 할 일 1건")).toBeVisible();

    await page.getByRole("tab", { name: "E2E 원목 도마" }).click();
    await expect(page.getByText("사입 가능").first()).toBeVisible();
});
