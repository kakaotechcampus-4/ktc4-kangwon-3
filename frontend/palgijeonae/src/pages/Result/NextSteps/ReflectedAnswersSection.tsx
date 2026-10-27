import type { Question } from "@/api/product";

interface ReflectedAnswersSectionProps {
    questions: Question[]
}

// TODO: 회차·순서로 정렬해서 렌더링하고, helpText/answerText null 처리, 빈 배열이면 섹션 자체를 숨김
function ReflectedAnswersSection({ questions }: ReflectedAnswersSectionProps) {
    return (
        <div>
            진단에 반영된 답변 섹션입니다. ({questions.length}건)
        </div>
    );
}

export default ReflectedAnswersSection;
