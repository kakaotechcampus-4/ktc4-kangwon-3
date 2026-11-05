import { type Page } from "@playwright/test";

// 진단은 mock-ai 기준 상품마다 몇 초가 걸린다. 결과가 나올 때까지 기다리는 상한.
export const DIAGNOSIS_TIMEOUT = 30_000;

// 업로드 화면에서 텍스트로 상품을 담는다. content에 [e2e:표시]를 넣으면 mock-ai가 그 결과로 진행한다.
export async function addTextProduct(page: Page, productName: string, content: string) {
    await page.getByRole("button", { name: "텍스트 / 이미지" }).click();
    await page.getByLabel("제품명").fill(productName);
    await page.getByLabel("제품 상세페이지 내용").fill(content);
    await page.getByRole("button", { name: "상품 추가하기" }).click();
}

// 업로드 화면에서 URL로 상품을 담는다. URL에 e2e=표시를 넣으면 mock-ai가 그 결과로 진행한다.
export async function addUrlProduct(page: Page, productName: string, url: string) {
    await page.getByRole("button", { name: "URL", exact: true }).click();
    await page.getByLabel("제품명").fill(productName);
    await page.getByLabel("제품 상세페이지 링크").fill(url);
    await page.getByRole("button", { name: "상품 추가하기" }).click();
}

// 텍스트 상품 하나로 진단을 요청하고 진행 화면으로 이동한다.
export async function startTextDiagnosis(page: Page, productName: string, content: string) {
    await page.goto("/upload");
    await addTextProduct(page, productName, content);
    await page.getByRole("button", { name: "진단 시작하기" }).click();
    await page.waitForURL(/\/judgement\/[0-9a-f-]{36}$/);
}
