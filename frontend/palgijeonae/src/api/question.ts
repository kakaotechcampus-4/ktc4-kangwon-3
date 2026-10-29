import type { AnswerSubmission } from "@/pages/Question/types";

/**
 * 답변을 제출한다.
 * TODO: 지금은 목업으로 성공 처리만 한다. 백엔드 연동 시 이 함수 내부만 실제 POST 호출로 교체한다.
 * @param _diagnosesId 답변을 제출할 진단서 id
 * @param _answers 제출할 답변 목록
 */
export async function submitAnswers(_diagnosesId: string, _answers: AnswerSubmission[]): Promise<void> {
    return;
}
