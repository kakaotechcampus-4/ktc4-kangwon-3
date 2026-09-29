import { useState } from "react";

import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import Question from "./Question";

// TODO: api 연동 기반을 마련하고 삭제할 목업 데이터
const productNames = ["제품 1", "제품 2", "제품 3"];

// TODO: api 연동 기반을 마련하고 삭제할 목업 데이터. 제품별 확인이 필요한 질문 목록.
const MOCK_QUESTIONS = [
    [
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
    [
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
    [
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
];

function QuestionPage() {
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});

    const handleAnswerChange = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단에 필요한 질문이 몇 가지 있어요" description="추가적인 확인이 필요한 정보들을 확인합니다. 제품 각각 입력해주세요."/>
            <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
            <div className="flex flex-col gap-4">
                {MOCK_QUESTIONS[selectedProductIndex].map((question, index) => (
                    <Question
                        key={question.id}
                        questionNumber={index + 1}
                        title={question.title}
                        description={question.description}
                        answer={answers[question.id] ?? ""}
                        onChange={(value) => handleAnswerChange(question.id, value)}
                    />
                ))}
            </div>
        </div>
     );
}

export default QuestionPage;
