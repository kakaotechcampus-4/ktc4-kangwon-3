import PreviewFrame from "@/components/common/PreviewFrame";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/constants";
import ProgressSummary from "@/pages/Question/components/ProgressSummary";
import QuestionCard from "@/pages/Question/components/QuestionCard";

const QUESTIONS = PREVIEW_PRODUCTS.slipperAwaiting.questions;

/** 메인 페이지 미리보기: 질문 답변 화면. */
function QuestionSlide() {
    return (
        <PreviewFrame label="질문 답변 화면 미리보기" baseWidth={1000} maxHeight={520} mobileMaxHeight={660}>
            <div className="flex w-full flex-col gap-6">
                <ProgressSummary currentAnswered={QUESTIONS.map((question) => Boolean(question.answerText))} />
                <div className="flex flex-col gap-4">
                    {QUESTIONS.map((question, index) => (
                        <QuestionCard
                            key={question.questionId}
                            id={`preview-slide-question-${question.questionId}`}
                            questionNumber={index + 1}
                            title={question.questionText}
                            description={question.helpText ?? ""}
                            answer={question.answerText ?? ""}
                            onChange={NOOP}
                        />
                    ))}
                </div>
            </div>
        </PreviewFrame>
    );
}

export default QuestionSlide;
