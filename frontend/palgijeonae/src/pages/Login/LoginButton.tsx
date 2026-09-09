interface LoginButtonProps {
    type: string
    image: string
    BorderColor: string
    BackgroundColor: string
    textColor: string
    onClick: () => void
}

function LoginButton({ type, image, BorderColor, BackgroundColor, textColor, onClick }: LoginButtonProps) {
    return (
        <button
            className={`flex flex-row cursor-pointer items-center justify-center gap-5 self-stretch rounded-xl border ${BorderColor} ${BackgroundColor} py-2.5 pr-8 pl-5`}
            onClick={onClick}
        >
            <img src={image} alt={`${type} logo`} className="h-9 w-9 shrink-0 rounded-[10px] object-cover" />
            <span className={`text-lg leading-7 font-semibold ${textColor}`}>{type} 계정으로 로그인</span>
        </button>
    )
}

export default LoginButton