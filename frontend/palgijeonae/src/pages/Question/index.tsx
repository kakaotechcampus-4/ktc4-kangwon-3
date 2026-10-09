import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate, useParams } from "react-router-dom";

import { getQuestions, submitAnswers } from "@/api/question";
import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import ProgressSummary from "./ProgressSummary";
import Question from "./Question";
import type { ProductQuestions } from "./types";
import { ProductStatus } from "./types";

// data가 로딩 중(undefined)일 때 매 렌더 새 배열이 생기지 않도록 고정된 레퍼런스를 재사용한다.
const EMPTY_PRODUCT_QUESTIONS: ProductQuestions[] = [];

interface AnswerState {
    answeredMatrix: boolean[][]
    productStatuses: ProductStatus[]
    firstUnanswered: { productIndex: number; questionId: string } | null
}

// 진행 표시(ProgressSummary)와 제출 전 미답변 검증이 공유하는 답변 판정 결과를 계산한다.
function computeAnswerState(questions: ProductQuestions[], answers: Record<string, string>): AnswerState {
    const isAnswered = (questionId: string) => Boolean(answers[questionId]?.trim());

    // [제품][질문] 답변 여부
    const answeredMatrix = questions.map((product) =>
        product.questions.map((question) => isAnswered(question.id)),
    );

    const productStatuses = answeredMatrix.map((row): ProductStatus => {
        const answeredCount = row.filter(Boolean).length;
        if (answeredCount === 0) return ProductStatus.Empty;
        return answeredCount === row.length ? ProductStatus.Complete : ProductStatus.Partial;
    });

    let firstUnanswered: { productIndex: number; questionId: string } | null = null;
    for (const [productIndex, row] of answeredMatrix.entries()) {
        const questionIndex = row.indexOf(false);
        if (questionIndex !== -1) {
            firstUnanswered = { productIndex, questionId: questions[productIndex].questions[questionIndex].id };
            break;
        }
    }

    return { answeredMatrix, productStatuses, firstUnanswered };
}

function QuestionPage() {
    const { diagnosesId } = useParams<{ diagnosesId?: string }>();
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const navigate = useNavigate();

    // diagnosesId가 없거나, undefined/null이 문자 그대로 들어온 경우
    const isMissingDiagnosesId = !diagnosesId || diagnosesId === "undefined" || diagnosesId === "null";

    // diagnosesId 없이 잘못 진입한 경우(예: /question/undefined) 요청을 보내지 않고 업로드 페이지로 되돌린다.
    useEffect(() => {
        if (isMissingDiagnosesId) {
            alert("잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.");
            navigate("/upload", { replace: true });
        }
    }, [isMissingDiagnosesId, navigate]);


    const { data, isPending: isQuestionsPending, isError: isQuestionsError, refetch: refetchQuestions } = useQuery({
        queryKey: ["questions", diagnosesId],
        queryFn: () => getQuestions(diagnosesId!),
        enabled: !isMissingDiagnosesId,
    });

    // 질문 데이터에서 화면에 필요한 파생값(기본값 적용, 탭 이름, 현재 선택된 질문)을 꺼낸다.
    const productQuestions = data ?? EMPTY_PRODUCT_QUESTIONS;
    const productNames = productQuestions.map((product) => product.productName);
    const currentQuestions = productQuestions[selectedProductIndex]?.questions ?? [];


    // 진행 표시(ProgressSummary)와 제출 전 미답변 검증이 같은 답변 판정 결과를 공유하도록 한 번에 계산
    const { answeredMatrix, productStatuses, firstUnanswered } = useMemo(
        () => computeAnswerState(productQuestions, answers),
        [productQuestions, answers],
    );

    const currentAnswered = answeredMatrix[selectedProductIndex] ?? [];


    const { mutate: runSubmitAnswers, isPending: isSubmitting } = useMutation({
        // TODO: 질문이 0개인 진단서는 answers가 빈 배열로 제출된다. 백엔드 연동 시 백엔드 제약조건에 따라 처리 필요
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

    const handlePrevProduct = () => {
        setSelectedProductIndex((prev) => prev - 1);
    };

    const handleNextProduct = () => {
        setSelectedProductIndex((prev) => prev + 1);
    };


    // 답변하지 않은 질문의 textarea를 포커스하고 스크롤하는 함수
    const focusQuestion = (questionId: string) => {
        const element = document.getElementById(questionId);
        element?.focus();
        element?.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    // 미답변 질문으로 포커싱하면서 유발된 탭 전환인 경우, 아래 scrollToTop effect를 한 번 건너뛴다.
    const skipScrollToTopRef = useRef(false);

    const handleSubmitAnswers = () => {
        if (firstUnanswered) {
            alert("질문에 모두 답변해 주세요.");
            if (firstUnanswered.productIndex !== selectedProductIndex) {
                // 다른 제품의 질문이면 flushSync로 탭 전환을 동기 렌더링한 다음 포커싱한다.
                skipScrollToTopRef.current = true;
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
        if (skipScrollToTopRef.current) {
            skipScrollToTopRef.current = false;
            return;
        }
        window.scrollTo({ top: 0, behavior: "smooth" });
    }, [selectedProductIndex]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단에 필요한 질문이 몇 가지 있어요" description="상세페이지만으로는 판단이 어려운 부분이에요. 제품마다 답해 주시면 진단서에 반영됩니다." />
            {isQuestionsPending ? (
                <div className="flex w-full justify-center py-12">
                    <div className="h-10 w-10 animate-spin rounded-full border-4 border-neutral-border border-t-white" />
                </div>

            ) : isQuestionsError ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">질문을 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={() => refetchQuestions()}
                        className="text-sm font-medium cursor-pointer text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>

            ) : productQuestions.length === 0 ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-neutral-border">확인이 필요한 질문이 없어요.</p>
                    <div className="flex w-full justify-end mt-10">
                        <Button text="진단서 확인하기" onClick={handleSubmitAnswers} fontSize={15} disabled={isSubmitting} />
                    </div>
                </div>

            ) : (
                <>
                    <div className="flex flex-col gap-3">
                        <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
                        <ProgressSummary currentAnswered={currentAnswered} productStatuses={productStatuses} />
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
                    <div className="flex w-full items-center justify-between">
                        <Button
                            text="← 이전 상품"
                            onClick={handlePrevProduct}
                            fontSize={15}
                            variant="secondary"
                            disabled={selectedProductIndex === 0}
                        />
                        <div className="flex gap-2.5">
                            <Button
                                text="다음 상품으로 →"
                                onClick={handleNextProduct}
                                fontSize={15}
                                variant="secondary"
                                disabled={selectedProductIndex === productQuestions.length - 1}
                            />
                            <Button text="답변 완료하기" onClick={handleSubmitAnswers} fontSize={15} disabled={isSubmitting} />
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default QuestionPage;
