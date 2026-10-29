import type { Question } from "@/api/product";

// questions[]엔 과거 회차 답변까지 누적돼서 내려온다. 지금 답해야 하는 가장 최근 회차(questionRound)만 추린다.
export function getCurrentRoundQuestions(questions: Question[]): Question[] {
    if (questions.length === 0) {
        return [];
    }

    const latestRound = Math.max(...questions.map((question) => question.questionRound));
    return questions.filter((question) => question.questionRound === latestRound);
}
