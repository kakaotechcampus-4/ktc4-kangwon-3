import type { AnswerSubmission } from "@/pages/Question/types";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/question" 대신 "@/api/mock/questionMock"으로 바꾸면 된다.
 */

/** 개발용 답변 제출 함수. 실제로는 아무 요청도 보내지 않고 성공 처리만 한다. */
export async function submitAnswers(_productId: string, _answers: AnswerSubmission[]): Promise<void> {
    return;
}
