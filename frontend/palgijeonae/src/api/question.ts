import apiClient from "@/api/client";
import type { AnswerSubmission } from "@/pages/Question/types";

/**
 * 답변을 제출한다. 제출하면 상품은 다시 진행 중(IN_PROGRESS)이 되고, 이어진 진단에서 질문이 한 번 더 올 수 있다(최대 2회차).
 * @param productId 답변을 제출할 상품 id
 * @param answers 지금 기다리는 회차의 질문 전체에 대한 답변 목록
 */
export async function submitAnswers(productId: string, answers: AnswerSubmission[]): Promise<void> {
    await apiClient.post(`/api/v1/products/${productId}/answers`, { answers });
}
