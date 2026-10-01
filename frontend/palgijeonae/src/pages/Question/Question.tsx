import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";

interface QuestionProps {
    id: string
    questionNumber: number
    title: string
    description: string
    answer: string
    onChange: (value: string) => void
}

function Question({id, questionNumber, title, description, answer, onChange}: QuestionProps) {
    return (
        <DefaultBox align="left">
            <div className="flex flex-col gap-4 w-full">
                <SectionIntro title={`${questionNumber}. ${title}`} description={description} size="xl" />
                <textarea id={id}
                        value={answer}
                        aria-label={title}
                        onChange={(e) => onChange(e.target.value)}
                        className="box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border min-h-30 max-h-50 py-2"
                        placeholder="주어진 질문에 자유롭게 답변하세요. 답변 분석은 AI가 합니다."></textarea>
            </div>
        </DefaultBox>
     );
}

export default Question;