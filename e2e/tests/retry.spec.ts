import { expect, test } from "../fixtures/auth";
import { DIAGNOSIS_TIMEOUT, startTextDiagnosis } from "../helpers/upload";

test("진단이 실패하면 다시 시도할 수 있고, 다시 진행한 진단의 결과를 확인할 수 있다", async ({ page }) => {
    // given: 첫 실행만 실패하는 상품
    await startTextDiagnosis(page, "E2E 전동 칫솔", "[e2e:failed] 충전식 전동 칫솔");
    await page.getByRole("button", { name: "진단서 보기 →" }).click({ timeout: DIAGNOSIS_TIMEOUT });
    await expect(page).toHaveURL(/\/result\/diagnoses\/[0-9a-f-]{36}$/);
    await expect(page.getByText("진단에 실패했어요. 다시 시도해 주세요.")).toBeVisible();

    // when
    await page.getByRole("button", { name: "다시 시도 →" }).click();

    // then: 진행 화면으로 이동해 다시 진행하고, 끝나면 결과를 볼 수 있다.
    await expect(page).toHaveURL(/\/judgement\/[0-9a-f-]{36}$/);
    await page.getByRole("link", { name: "결과 보기" }).click({ timeout: DIAGNOSIS_TIMEOUT });
    await expect(page.getByText("구매 대행 가능").first()).toBeVisible();
});

test("다시 시도해도 같은 결과인 실패는 다시 시도를 권하지 않는다", async ({ page }) => {
    // given: 재시도할 수 없는 실패로 끝나는 상품
    await startTextDiagnosis(page, "E2E 빈 상세페이지", "[e2e:failed-final] 내용 없음");

    // when
    await page.getByRole("button", { name: "진단서 보기 →" }).click({ timeout: DIAGNOSIS_TIMEOUT });

    // then
    await expect(page.getByText("진단을 완료할 수 없어요.")).toBeVisible();
    await expect(page.getByRole("button", { name: "다시 시도 →" })).toHaveCount(0);
});
