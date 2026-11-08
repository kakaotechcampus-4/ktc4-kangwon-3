import { MOCK_PRODUCT_RESULTS } from "@/api/mock/data/productResults";
import { removeProductFromLawAmendments } from "@/api/mock/lawAmendments";
import type { ProductResult } from "@/api/types/product";
import type { AnswerSubmission } from "@/pages/Question/types";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/products" 대신 "@/api/mock/products"로 바꾸면 된다.
 */

/** 개발용 상품 단건 조회 함수 */
export async function getProduct(_productId: string): Promise<ProductResult> {
    return MOCK_PRODUCT_RESULTS[5];
}

/** 개발용 답변 제출 함수. 실제로는 아무 요청도 보내지 않고 성공 처리만 한다. */
export async function submitAnswers(_productId: string, _answers: AnswerSubmission[]): Promise<void> {
    return;
}

/** 개발용 재진단 함수. 요청은 보내지 않고, 목업 개정 목록에서 그 상품만 뺀다. */
export async function rediagnoseProduct(productId: string): Promise<void> {
    removeProductFromLawAmendments(productId);
}
