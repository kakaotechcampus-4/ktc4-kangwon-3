import Button from "@/components/common/Button";
import PreviewFrame from "@/components/common/PreviewFrame";
import SectionIntro from "@/components/common/SectionIntro";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import ProgressSummary from "@/pages/Question/ProgressSummary";
import Question from "@/pages/Question/Question";

const QUESTIONS = PREVIEW_PRODUCTS.slipperAwaiting.questions;

/** 메인 페이지 미리보기: 질문 답변 화면. */
function QuestionSlide() {
    return (
        <PreviewFrame label="질문 답변 화면 미리보기">
            <div className="flex w-full flex-col gap-8">
                <SectionIntro
                    title="1차 질문"
                    description="상세페이지만으로는 판단이 어려운 부분이에요. 답해 주시면 진단서에 반영됩니다."
                />
                <div className="flex w-full flex-col gap-6">
                    <ProgressSummary currentAnswered={QUESTIONS.map((question) => Boolean(question.answerText))} />
                    <div className="flex flex-col gap-4">
                        {QUESTIONS.map((question, index) => (
                            <Question
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
                    <div className="flex w-full justify-end">
                        <Button text="답변 완료하기" onClick={NOOP} fontSize={15} />
                    </div>
                </div>
            </div>
        </PreviewFrame>
    );
}

export default QuestionSlide;
