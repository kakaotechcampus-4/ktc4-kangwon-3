import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate, useParams } from "react-router-dom";

import { getQuestions, submitAnswers } from "@/api/question";
import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import ProgressSummary from "./ProgressSummary";
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

    // 진행 표시(ProgressSummary)와 제출 전 미답변 검증이 같은 답변 판정 결과를 공유하도록 한 번에 계산한다.
    const { answeredMatrix, productRatios, firstUnanswered } = useMemo(() => {
        const questions = data ?? [];
        const isAnswered = (questionId: string) => Boolean(answers[questionId]?.trim());

        // [제품][질문] 답변 여부
        const answeredMatrix = questions.map((product) =>
            product.questions.map((question) => isAnswered(question.id)),
        );

        const productRatios = answeredMatrix.map((row) => row.filter(Boolean).length / (row.length || 1));

        let firstUnanswered: { productIndex: number; questionId: string } | null = null;
        for (const [productIndex, row] of answeredMatrix.entries()) {
            const questionIndex = row.indexOf(false);
            if (questionIndex !== -1) {
                firstUnanswered = { productIndex, questionId: questions[productIndex].questions[questionIndex].id };
                break;
            }
        }

        return { answeredMatrix, productRatios, firstUnanswered };
    }, [data, answers]);

    // 탭 전환은 계산된 결과에서 꺼내기만 한다.
    const currentQuestions = productQuestions[selectedProductIndex]?.questions ?? [];
    const currentAnswered = answeredMatrix[selectedProductIndex] ?? [];

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

    // 답변하지 않은 질문의 textarea를 포커스하고 스크롤하는 함수
    const focusQuestion = (questionId: string) => {
        const element = document.getElementById(questionId);
        element?.focus();
        element?.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    const handleSubmitAnswers = () => {
        if (firstUnanswered) {
            alert("질문에 모두 답변해 주세요.");
            if (firstUnanswered.productIndex !== selectedProductIndex) {
                // 다른 제품의 질문이면 flushSync로 탭 전환을 동기 렌더링한 다음 포커싱한다.
                flushSync(() => {
                    setSelectedProductIndex(firstUnanswered.productIndex);
                });
            }
            focusQuestion(firstUnanswered.questionId);
            return;
        }

        runSubmitAnswers();
    };

    useEffect(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    }, [selectedProductIndex]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단에 필요한 질문이 몇 가지 있어요" description="추가적인 확인이 필요한 정보들을 확인합니다. 제품 각각 입력해주세요." />
            <div className="flex flex-col gap-3">
                <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
                <ProgressSummary currentAnswered={currentAnswered} productRatios={productRatios} />
            </div>
            <div className="flex flex-col gap-4">
                {currentQuestions.map((question, index) => (
                    <Question
                        key={question.id}
                        id={question.id}
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
