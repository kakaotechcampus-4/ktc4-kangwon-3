// TODO: AI 파이프라인이 연결되면 아래 import문의 주석을 풀기
// import apiClient from "@/api/client";
import type { AnswerSubmission } from "@/pages/Question/types";

/**
 * 답변을 제출한다. 제출하면 상품은 다시 진행 중(IN_PROGRESS)이 되고, 이어진 진단에서 질문이 한 번 더 올 수 있다(최대 2회차).
 * TODO: 지금은 목업으로 성공 처리만 한다. 백엔드 연동 시 이 함수 내부만 실제 POST 호출로 교체한다.
 * @param _productId 답변을 제출할 상품 id
 * @param _answers 지금 기다리는 회차의 질문 전체에 대한 답변 목록
 */
export async function submitAnswers(_productId: string, _answers: AnswerSubmission[]): Promise<void> {
    // await apiClient.post(`/api/v1/products/${productId}/answers`, { answers: _answers });
    return;
}
