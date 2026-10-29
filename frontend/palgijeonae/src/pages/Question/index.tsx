import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { submitAnswers } from "@/api/question";
import { ProcessingStatusType } from "@/api/types";
import Button from "@/components/common/Button";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ProductPreview from "@/components/common/ProductPreview";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingRouteParam } from "@/lib/routeParams";

import { computeAnswerState } from "./answerState";
import { getCurrentRoundQuestions } from "./currentQuestions";
import ProgressSummary from "./ProgressSummary";
import Question from "./Question";
import { useQuestionProduct } from "./useQuestionProduct";

function QuestionPage() {
    const { productId } = useParams<{ productId?: string }>();
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const navigate = useNavigate();

    const isInvalidAccess = isMissingRouteParam(productId);

    // productId 없이 잘못 진입한 경우(예: /question/undefined) 요청을 보내지 않고 업로드 페이지로 되돌린다.
    useEffect(() => {
        if (isInvalidAccess) {
            alert("잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.");
            navigate("/upload", { replace: true });
        }
    }, [isInvalidAccess, navigate]);

    const { data: product, isPending, isError, refetch } = useQuestionProduct(productId, !isInvalidAccess);

    const isNotAwaitingInput = product != null && product.processingStatus !== ProcessingStatusType.AwaitingInput;

    // 답변 대기 중이 아닌 상품에 URL로 직접 접근한 경우 결과 페이지로 돌려보낸다.
    useEffect(() => {
        if (isNotAwaitingInput) {
            alert("잘못된 접근입니다.");
            navigate(`/result/product/${productId}`, { replace: true });
        }
    }, [isNotAwaitingInput, productId, navigate]);

    const currentQuestions = getCurrentRoundQuestions(product?.questions ?? []);
    const currentRound = currentQuestions[0]?.questionRound;
    const { currentAnswered, firstUnansweredId } = computeAnswerState(currentQuestions, answers);

    const { mutate: runSubmitAnswers, isPending: isSubmitting } = useMutation({
        mutationFn: () =>
            submitAnswers(
                productId!,
                currentQuestions.map((question) => ({ questionId: question.questionId, answerText: answers[question.questionId] })),
            ),
        onSuccess: () => {
            navigate(`/judgement/${product!.diagnosesId}`);
        },
        onError: (error) => {
            alert(error instanceof Error ? error.message : "답변 제출에 실패했습니다. 다시 시도해주세요.");
        },
    });

    const handleAnswerChange = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    // 답변하지 않은 질문의 textarea를 포커스하고 스크롤한다.
    const focusQuestion = (questionId: string) => {
        const element = document.getElementById(questionId);
        element?.focus();
        element?.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    const handleSubmitAnswers = () => {
        if (firstUnansweredId) {
            alert("질문에 모두 답변해 주세요.");
            focusQuestion(firstUnansweredId);
            return;
        }

        runSubmitAnswers();
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro
                title={currentRound ? `${currentRound}차 질문` : "진단에 필요한 질문이 몇 가지 있어요"}
                description="상세페이지만으로는 판단이 어려운 부분이에요. 답해 주시면 진단서에 반영됩니다."
            />
            {isPending ? (
                <LoadingSpinner />
            ) : isError ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">질문을 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="text-sm font-medium cursor-pointer text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>

            ) : !product || currentQuestions.length === 0 ? (
                <p className="w-full py-12 text-center text-sm font-medium text-neutral-border">
                    확인이 필요한 질문이 없어요.
                </p>

            ) : (
                <div className="flex w-full flex-col gap-6">
                    <ProductPreview
                        productName={product.productName}
                        productImageUrl={product.productImageUrl}
                        resultStatus={product.resultStatus}
                        processingStatus={product.processingStatus}
                        sourceType={product.sourceType}
                    />
                    <ProgressSummary currentAnswered={currentAnswered} />
                    <div className="flex flex-col gap-4">
                        {currentQuestions.map((question, index) => (
                            <Question
                                key={question.questionId}
                                id={question.questionId}
                                questionNumber={index + 1}
                                title={question.questionText}
                                description={question.helpText ?? ""}
                                answer={answers[question.questionId] ?? ""}
                                onChange={(value) => handleAnswerChange(question.questionId, value)}
                            />
                        ))}
                    </div>
                    <div className="flex w-full justify-end">
                        <Button text="답변 완료하기" onClick={handleSubmitAnswers} fontSize={15} disabled={isSubmitting} />
                    </div>
                </div>
            )}
        </div>
    );
}

export default QuestionPage;
