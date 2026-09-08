interface ButtonProps {
    text: string
    onClick: () => void
    fontSize?: number
}

function Button({ text, onClick, fontSize = 20 }: ButtonProps) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="flex cursor-pointer items-center justify-center gap-2.5 rounded-[10px] bg-primary px-[25px] py-[14px] font-bold leading-[1.2] text-center text-white"
            style={{ fontSize: `${fontSize}px` }}
        >
            {text}
        </button>
    );
}

export default Button;
