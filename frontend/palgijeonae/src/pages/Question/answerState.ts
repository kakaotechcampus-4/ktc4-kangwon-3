import { type ProductQuestions, ProductStatus } from "./types";

export interface AnswerState {
    answeredMatrix: boolean[][]
    productStatuses: ProductStatus[]
    firstUnanswered: { productIndex: number; questionId: string } | null
}

// 진행 표시(ProgressSummary)와 제출 전 미답변 검증이 공유하는 답변 판정 결과를 계산한다.
export function computeAnswerState(questions: ProductQuestions[], answers: Record<string, string>): AnswerState {
    const isAnswered = (questionId: string) => Boolean(answers[questionId]?.trim());

    const answeredMatrix: boolean[][] = [];
    const productStatuses: ProductStatus[] = [];
    let firstUnanswered: { productIndex: number; questionId: string } | null = null;

    for (const [productIndex, product] of questions.entries()) {
        // 해당 제품에 대한 [질문] 답변 여부
        const row: boolean[] = [];
        let answeredCount = 0;

        for (const question of product.questions) {
            const answered = isAnswered(question.id);
            row.push(answered);
            if (answered) {
                answeredCount++;
            } else if (!firstUnanswered) {
                // 가장 먼저 만난 미답변 질문만 기록한다.
                firstUnanswered = { productIndex, questionId: question.id };
            }
        }

        answeredMatrix.push(row);
        productStatuses.push(
            answeredCount === 0
                ? ProductStatus.Empty
                : answeredCount === row.length
                    ? ProductStatus.Complete
                    : ProductStatus.Partial,
        );
    }

    return { answeredMatrix, productStatuses, firstUnanswered };
}
