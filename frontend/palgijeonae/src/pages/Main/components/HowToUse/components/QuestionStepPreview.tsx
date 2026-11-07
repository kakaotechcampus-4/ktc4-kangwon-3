import PreviewFrame from "@/components/common/PreviewFrame";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/constants";
import QuestionCard from "@/pages/Question/components/QuestionCard";

const QUESTION = PREVIEW_PRODUCTS.slipperAwaiting.questions[0];

/** 사용 방법 3단계 미리보기: 답변을 채운 질문 1개. */
function QuestionStepPreview() {
    return (
        <PreviewFrame label="질문 답변 화면 미리보기" baseWidth={600}>
            <QuestionCard
                id={`preview-step-question-${QUESTION.questionId}`}
                questionNumber={1}
                title={QUESTION.questionText}
                description={QUESTION.helpText ?? ""}
                answer={QUESTION.answerText ?? ""}
                onChange={NOOP}
            />
        </PreviewFrame>
    );
}

export default QuestionStepPreview;
