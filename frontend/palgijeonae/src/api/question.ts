import type { AnswerSubmission, ProductQuestions } from "@/pages/Question/types";

// TODO: 백엔드 연동 전까지 쓰는 목업 데이터. 연동 시 이 파일 내부만 실제 GET 호출로 교체한다.
const MOCK_PRODUCT_QUESTIONS: ProductQuestions[] = [
    {
        productId: "product-1",
        productName: "제품 1",
        questions: [
            {
                id: "product1-q1",
                title: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
                description: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
            },
            {
                id: "product1-q2",
                title: "실제로 주로 판매하는 대상 연령은?",
                description: "상세페이지에 \"3-6세\"와 \"14세 이상\"이 함께 적혀 있으면 확인이 필요합니다.",
            },
            {
                id: "product1-q3",
                title: "공급사가 KC 관련 서류(시험성적서·확인서 등)를 갖고 있나요?",
                description: "서류가 없으면 통관 및 판매가 제한될 수 있습니다.",
            },
        ],
    },
    {
        productId: "product-2",
        productName: "제품 2",
        questions: [
            {
                id: "product2-q1",
                title: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
                description: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
            },
            {
                id: "product2-q2",
                title: "상세페이지에 적힌 소재/성분 정보가 실제 제품과 동일한가요?",
                description: "상세페이지와 실제 제품의 소재가 다르면 재확인이 필요합니다.",
            },
            {
                id: "product2-q3",
                title: "해외에서 직접 제조된 상품인가요?",
                description: "해외 제조 상품은 추가 인증이 필요할 수 있습니다.",
            },
        ],
    },
    {
        productId: "product-3",
        productName: "제품 3",
        questions: [
            {
                id: "product3-q1",
                title: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
                description: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
            },
            {
                id: "product3-q2",
                title: "실제로 주로 판매하는 대상 연령은?",
                description: "상세페이지에 \"3-6세\"와 \"14세 이상\"이 함께 적혀 있으면 확인이 필요합니다.",
            },
            {
                id: "product3-q3",
                title: "동일한 상품을 이미 다른 채널에서 판매한 이력이 있나요?",
                description: "판매 이력이 있다면 기존 인증/신고 내역을 함께 확인합니다.",
            },
        ],
    },
];

// TODO: 언더바 접두사는 미사용 매개변수 표시 관례로, 연동 시 실제로 사용하게 되면 제거한다.

/**
 * 확인이 필요한 질문 목록을 상품별로 가져온다.
 * TODO: 지금은 diagnosesId와 무관하게 고정된 목업 데이터를 반환한다. 백엔드 연동 시 이 함수 내부만 실제 GET 호출로 교체한다.
 * @param _diagnosesId 질문을 조회할 진단서 id
 * @returns 상품별 질문 목록
 */
export async function getQuestions(_diagnosesId: string): Promise<ProductQuestions[]> {
    return MOCK_PRODUCT_QUESTIONS;
}

/**
 * 답변을 제출한다.
 * TODO: 지금은 목업으로 성공 처리만 한다. 백엔드 연동 시 이 함수 내부만 실제 POST 호출로 교체한다.
 * @param _diagnosesId 답변을 제출할 진단서 id
 * @param _answers 제출할 답변 목록
 */
export async function submitAnswers(_diagnosesId: string, _answers: AnswerSubmission[]): Promise<void> {
    return;
}



