import type { Question } from "@/api/product";

export interface AnswerState {
    currentAnswered: boolean[]
    firstUnansweredId: string | null
}

// 질문별 답변 여부와 가장 먼저 만난 미답변 질문을 한 번의 순회로 함께 계산한다.
export function computeAnswerState(questions: Question[], answers: Record<string, string>): AnswerState {
    const currentAnswered: boolean[] = [];
    let firstUnansweredId: string | null = null;

    for (const question of questions) {
        const answered = Boolean(answers[question.questionId]?.trim());
        currentAnswered.push(answered);
        if (!answered && firstUnansweredId === null) {
            firstUnansweredId = question.questionId;
        }
    }

    return { currentAnswered, firstUnansweredId };
}
