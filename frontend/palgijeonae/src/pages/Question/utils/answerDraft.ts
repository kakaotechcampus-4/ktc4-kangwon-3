// 추가 질문의 작성 중인 답변을 새로고침해도 이어 쓸 수 있도록 sessionStorage에 임시 저장한다. 탭을 닫으면 사라지고, 로그아웃하면 모두 지운다.
const DRAFT_KEY_PREFIX = "question-draft:";

export type AnswerDraft = Record<string, string>;

// 질문 회차마다 따로 저장해서, 다음 회차 질문에 지난 회차 답변이 섞이지 않게 한다.
const getDraftKey = (productId: string, questionRound: number) => `${DRAFT_KEY_PREFIX}${productId}:${questionRound}`;

// 저장소를 쓸 수 없는 환경(사생활 보호 모드, 용량 초과 등)에서도 화면은 그대로 동작해야 하므로, 모든 접근을 try/catch로 감싼다.
export function loadAnswerDraft(productId: string, questionRound: number): AnswerDraft {
    try {
        const raw = sessionStorage.getItem(getDraftKey(productId, questionRound));
        if (!raw) {
            return {};
        }

        const parsed: unknown = JSON.parse(raw);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
            return {};
        }

        return Object.fromEntries(Object.entries(parsed).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
    } catch {
        return {};
    }
}

// 모든 답변이 비어 있으면 저장하지 않고 지운다.
export function saveAnswerDraft(productId: string, questionRound: number, answers: AnswerDraft): void {
    try {
        const key = getDraftKey(productId, questionRound);
        if (Object.values(answers).every((answer) => !answer.trim())) {
            sessionStorage.removeItem(key);
            return;
        }

        sessionStorage.setItem(key, JSON.stringify(answers));
    } catch {
        // 임시 저장은 부가 기능이라 실패해도 입력은 계속 할 수 있다.
    }
}

export function clearAnswerDraft(productId: string, questionRound: number): void {
    try {
        sessionStorage.removeItem(getDraftKey(productId, questionRound));
    } catch {
        // 지우지 못해도 다음 제출이나 로그아웃에서 다시 정리된다.
    }
}

// 로그아웃할 때 다른 회원의 답변이 남지 않도록 모든 상품·회차의 임시 저장을 지운다.
export function clearAllAnswerDrafts(): void {
    try {
        const keys = Array.from({ length: sessionStorage.length }, (_, index) => sessionStorage.key(index));
        keys.forEach((key) => {
            if (key?.startsWith(DRAFT_KEY_PREFIX)) {
                sessionStorage.removeItem(key);
            }
        });
    } catch {
        // 지우지 못해도 탭을 닫으면 사라진다.
    }
}

// 현재 회차 질문에 없는 questionId의 답변은 버린다.
export function pickAnswersForQuestions(draft: AnswerDraft, questionIds: string[]): AnswerDraft {
    return Object.fromEntries(Object.entries(draft).filter(([questionId]) => questionIds.includes(questionId)));
}
