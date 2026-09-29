import DefaultBox from "@/components/common/DefaultBox";

interface QuestionProps {
    questionNumber: number
    title: string
    description: string
    answer: string
    onChange: (value: string) => void
}

function Question({questionNumber, title, description, answer, onChange}: QuestionProps) {
    return ( 
        <DefaultBox align="left">
            <div>
                <h3>{questionNumber}. {title}</h3>
                <p>{description}</p>
                <input value={answer} onChange={(e) => onChange(e.target.value)}></input>
            </div>
        </DefaultBox>
     );
}

export default Question;