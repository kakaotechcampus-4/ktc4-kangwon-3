import type { Question } from "@/api/types/product"
import DefaultBox from "@/components/common/DefaultBox";

interface ReflectedAnswerCardProps {
    question: Question
}

function ReflectedAnswerCard({ question }: ReflectedAnswerCardProps) {
    return (
        <DefaultBox>
            <div className="flex w-full flex-wrap items-center gap-2.5">
                <div className="rounded-full border border-box-line bg-white px-2.5 py-0.5">
                    <span className="text-xs leading-tight text-neutral-muted">{question.questionRound}차 질문</span>
                </div>
                <h3 className="text-base leading-tight font-bold text-black md:text-lg">{question.questionText}</h3>
            </div>
            <div className="flex w-full flex-col items-start gap-1 rounded-xl bg-primary/10 px-4.5 py-3.5 md:flex-row md:items-center md:gap-3">
                <h4 className="text-base font-bold text-primary">내 답변</h4>
                <p className="text-base leading-relaxed whitespace-pre-line text-black">{question.answerText ?? "답변 기록이 없어요."}</p>
            </div>
        </DefaultBox>
    );
}

export default ReflectedAnswerCard;