import { useCallback, useEffect, useMemo, useState } from "react";

import type { Question } from "@/api/types/product";
import { type AnswerDraft, clearAnswerDraft, loadAnswerDraft, pickAnswersForQuestions, saveAnswerDraft } from "@/pages/Question/utils/answerDraft";

/**
 * 현재 회차 질문의 답변 상태. 같은 회차에 저장된 임시 답변이 있으면 처음부터 채워 두고, 답변이 바뀔 때마다 임시 저장한다.
 * @param questions 지금 답해야 하는 회차의 질문들 (아직 불러오기 전이면 빈 배열)
 */
export function useAnswerDraft(productId: string | undefined, questions: Question[]) {
    const questionRound = questions[0]?.questionRound;
    // 질문 배열은 렌더마다 새로 만들어지므로, 저장소를 매번 읽지 않도록 id 문자열로 바뀜을 판단한다.
    const questionIdsKey = questions.map((question) => question.questionId).join("|");

    // 사용자가 이번 화면에서 직접 고친 답변. 복원한 값 위에 덮어쓴다.
    const [edits, setEdits] = useState<AnswerDraft>({});

    const restored = useMemo<AnswerDraft>(() => {
        if (!productId || questionRound === undefined) {
            return {};
        }
        return pickAnswersForQuestions(loadAnswerDraft(productId, questionRound), questionIdsKey.split("|"));
    }, [productId, questionRound, questionIdsKey]);

    const answers = useMemo(() => ({ ...restored, ...edits }), [restored, edits]);

    useEffect(() => {
        // 아직 아무것도 고치지 않았다면 복원한 값을 그대로 다시 저장할 필요가 없다.
        if (!productId || questionRound === undefined || Object.keys(edits).length === 0) {
            return;
        }
        saveAnswerDraft(productId, questionRound, answers);
    }, [productId, questionRound, edits, answers]);

    const setAnswer = useCallback((questionId: string, value: string) => {
        setEdits((prev) => ({ ...prev, [questionId]: value }));
    }, []);

    const clearDraft = useCallback(() => {
        if (productId && questionRound !== undefined) {
            clearAnswerDraft(productId, questionRound);
        }
    }, [productId, questionRound]);

    return { answers, setAnswer, clearDraft };
}
