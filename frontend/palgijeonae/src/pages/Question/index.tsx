import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getQuestions, submitAnswers } from "@/api/question";
import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import Question from "./Question";

function QuestionPage() {
    const { diagnosesId } = useParams<{ diagnosesId: string }>();
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const navigate = useNavigate();

    const { data } = useQuery({
        queryKey: ["questions", diagnosesId],
        queryFn: () => getQuestions(diagnosesId!),
    });

    // 로딩 중 undefined 방지용 기본값
    const productQuestions = data ?? [];

    // ProductTabs에 넘길 이름만 추출
    const productNames = productQuestions.map((product) => product.productName);

    const { mutate: runSubmitAnswers } = useMutation({
        mutationFn: () =>
            submitAnswers(
                diagnosesId!,
                Object.entries(answers).map(([questionId, answer]) => ({ questionId, answer })),
            ),
        onSuccess: () => {
            // TODO: 추후 result 페이지 구현 후 경로 파라미터로 교체 (/result/diagnosis/:diagnosisId)
            navigate("/result")
        },
        onError: (error) => {
            alert(error instanceof Error ? error.message : "답변 제출에 실패했습니다. 다시 시도해주세요.");
        },
    });

    const handleAnswerChange = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    const handleNextProduct = () => {
        setSelectedProductIndex(selectedProductIndex + 1);
    };

    const handleSubmitAnswers = () => {
        // TODO: 비어있는 입력 폼 검증도 추후 구현
        runSubmitAnswers();
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
