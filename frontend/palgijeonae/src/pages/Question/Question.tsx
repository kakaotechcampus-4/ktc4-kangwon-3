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

// 추후 결정되는 BE 응답 스키마 구성에 따라 placeholder도 props로 구성해야 할 수 있음.
function Question({ id, questionNumber, title, description, answer, onChange }: QuestionProps) {
    return (
        <DefaultBox align="left" className="focus-within:border-primary">
            <div className="flex flex-row items-start gap-4 w-full">
                <div className="w-8 h-8 shrink-0 rounded-full bg-primary/10 text-primary text-base font-semibold leading-none flex items-center justify-center">
                    {questionNumber}
                </div>
                <div className="flex flex-col w-full gap-4">
                    <SectionIntro title={title} description={description} size="xl" />
                    <textarea id={id}
                        value={answer}
                        aria-label={title}
                        onChange={(e) => onChange(e.target.value)}
                        className="box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border min-h-30 max-h-50 py-2 focus:border-primary focus:outline-none"
                        placeholder="주어진 질문에 자유롭게 답변하세요. 답변 분석은 AI가 합니다." />
                </div>
            </div>
        </DefaultBox>
    );
}

export default Question;