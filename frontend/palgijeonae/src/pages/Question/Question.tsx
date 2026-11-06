import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";
import { truncateToCodeUnitLength } from "@/lib/text";

interface QuestionProps {
    id: string
    questionNumber: number
    title: string
    description: string
    answer: string
    onChange: (value: string) => void
}

// BE가 answerText를 500자(코드 유닛 기준)까지만 허용한다.
const MAX_ANSWER_LENGTH = 500;

function Question({ id, questionNumber, title, description, answer, onChange }: QuestionProps) {
    // 네이티브 maxLength는 IME 조합 중엔 실시간으로 길이를 막지 못해서 직접 잘라준다.
    const handleChange = (value: string) => {
        onChange(truncateToCodeUnitLength(value, MAX_ANSWER_LENGTH));
    };

    return (
        <DefaultBox align="left" className="focus-within:border-primary">
            <div className="flex flex-row items-start gap-4 w-full">
                <div className="w-8 h-8 shrink-0 rounded-full bg-primary/10 text-primary text-base font-semibold leading-none flex items-center justify-center">
                    {questionNumber}
                </div>
                <div className="flex flex-col w-full gap-4">
                    <SectionIntro title={title} description={description} size="xl" />
                    <div className="flex w-full flex-col items-end gap-1">
                        <textarea id={id}
                            value={answer}
                            aria-label={title}
                            onChange={(e) => handleChange(e.target.value)}
                            maxLength={MAX_ANSWER_LENGTH}
                            className="box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border min-h-30 max-h-50 py-2 focus:border-primary"
                            placeholder="주어진 질문에 자유롭게 답변하세요. 답변 분석은 AI가 합니다." />
                        <span className="text-xs leading-3.5 text-neutral-border">{answer.length}/{MAX_ANSWER_LENGTH}</span>
                    </div>
                </div>
            </div>
        </DefaultBox>
    );
}

export default Question;