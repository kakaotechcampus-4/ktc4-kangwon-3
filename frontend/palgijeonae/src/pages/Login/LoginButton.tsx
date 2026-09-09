interface LoginButtonProps {
    type: String
    image: String
    BorderColor: String
    BackgroundColor: String
    textColor: String
    onClick: () => void
}

function LoginButton({ type, image, BorderColor, BackgroundColor, textColor, onClick }: LoginButtonProps) {
    return (
        <button
            className={`flex w-full flex-row items-center justify-center gap-2 rounded-10 border-[1px] border-${BorderColor} bg-${BackgroundColor} py-3 px-4`}
            onClick={onClick}
        >
            <img src={image} alt={`${type} logo`} className="h-6 w-6 shrink-0 object-contain" />
            <span className={`text-base font-semibold leading-4.5 text-${textColor}`}>{type} 계정으로 로그인</span>
        </button>
    )
}