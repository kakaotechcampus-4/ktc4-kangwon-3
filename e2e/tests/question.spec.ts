import { expect, test } from "../fixtures/auth";
import { DIAGNOSIS_TIMEOUT, startTextDiagnosis } from "../helpers/upload";

test("AI가 질문하면 답변을 제출하고, 이어진 진단의 결과를 확인할 수 있다", async ({ page }) => {
    // given: 첫 진단이 질문으로 끝나는 상품
    await startTextDiagnosis(page, "E2E 미니 가습기", "[e2e:question] USB 충전식 무선 미니 가습기");
    await page.getByRole("link", { name: "질문에 답변하기 →" }).click({ timeout: DIAGNOSIS_TIMEOUT });
    await expect(page).toHaveURL(/\/question\/[0-9a-f-]{36}$/);

    // when
    await page.getByLabel("제품에 배터리가 포함되어 있나요?").fill("네, 내장 리튬 배터리가 있습니다.");
    await page.getByLabel("사용 대상 연령이 어떻게 되나요?").fill("성인용입니다.");
    await page.getByRole("button", { name: "답변 완료하기" }).click();

    // then: 진행 화면으로 돌아가 이어진 진단이 끝나면 결과를 볼 수 있다.
    await expect(page).toHaveURL(/\/judgement\/[0-9a-f-]{36}$/);
    await page.getByRole("link", { name: "결과 보기" }).click({ timeout: DIAGNOSIS_TIMEOUT });
    await expect(page).toHaveURL(/\/result\/product\/[0-9a-f-]{36}$/);
    await expect(page.getByText("구매 대행 가능").first()).toBeVisible();
});
