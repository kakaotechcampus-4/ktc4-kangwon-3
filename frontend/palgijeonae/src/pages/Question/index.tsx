import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getQuestions } from "@/api/question";
import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import Question from "./Question";

function QuestionPage() {
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});

    // 상품별 확인 질문 목록 불러오기
    const { data } = useQuery({
        queryKey: ["questions"],
        queryFn: getQuestions,
    });
    const productQuestions = data ?? [];
    const productNames = productQuestions.map((product) => product.productName);

    const handleAnswerChange = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    const handleNextProduct = () => {
        setSelectedProductIndex(selectedProductIndex + 1);
    };

    const handleSubmitAnswers = () => {
        // TODO: 제출 로직은 추후 구현
        // 비어있는 입력 폼 검증도 추후 구현
    };

    // 상품이 바뀔 때(다음 상품으로 버튼, 탭 클릭) 화면 맨 위로 이동.
    useEffect(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    }, [selectedProductIndex]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단에 필요한 질문이 몇 가지 있어요" description="추가적인 확인이 필요한 정보들을 확인합니다. 제품 각각 입력해주세요."/>
            <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
            <div className="flex flex-col gap-4">
                {(productQuestions[selectedProductIndex]?.questions ?? []).map((question, index) => (
                    <Question
                        key={question.id}
                        questionNumber={index + 1}
                        title={question.title}
                        description={question.description ?? ""}
                        answer={answers[question.id] ?? ""}
                        onChange={(value) => handleAnswerChange(question.id, value)}
                    />
                ))}
            </div>
            <div className="flex w-full justify-end">
                {selectedProductIndex < productNames.length - 1 ?
                    (<Button text="다음 상품으로 →" onClick={handleNextProduct} fontSize={15} />) :
                    (<Button text="답변 완료하기" onClick={handleSubmitAnswers} fontSize={15} />)}
            </div>
        </div>
    );
}

export default QuestionPage;
