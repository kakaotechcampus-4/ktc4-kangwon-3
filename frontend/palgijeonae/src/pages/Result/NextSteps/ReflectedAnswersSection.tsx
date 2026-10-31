import type { Question } from "@/api/product";
import SectionIntro from "@/components/common/SectionIntro";

import ReflectedAnswerCard from "./ReflectedAnswerCard";

interface ReflectedAnswersSectionProps {
    questions: Question[]
}

function ReflectedAnswersSection({ questions }: ReflectedAnswersSectionProps) {
    if (questions.length === 0) {
        return null;
    }

    const sortedQuestions = questions.toSorted((a, b) =>
        a.questionRound - b.questionRound || a.questionOrder - b.questionOrder,
    );

    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="진단에 반영된 답변" description="진단에 반영된 질문과 사용자님이 입력하신 답변이에요" size="2xl"/>
            <div className="flex w-full flex-col gap-4">
                {sortedQuestions.map((question) => (
                    <ReflectedAnswerCard key={question.questionId} question={question} />
                ))}
            </div>
        </div>
    );
}

export default ReflectedAnswersSection;
