import { cva } from "class-variance-authority";

type Provider = 'kakao' | 'naver' | 'google';

const buttonVariants = cva(
    "flex flex-row cursor-pointer items-center justify-center gap-5 self-stretch rounded-xl border py-2.5 pr-8 pl-5",
    {
        variants: {
            provider: {
                kakao: "border-[#FEE500] bg-[#FEE500]",
                naver: "border-[#03A94D] bg-[#03A94D]",
                google: "border-[#747775] bg-white",
            },
        },
    },
);

const labelVariants = cva("text-lg leading-7 font-semibold", {
    variants: {
        provider: {
            kakao: "text-black/85",
            naver: "text-white",
            google: "text-[#1F1F1F]",
        },
    },
});

interface LoginButtonProps {
    provider: Provider
    label: string
    image: string
    onClick: () => void
}

function LoginButton({ provider, label, image, onClick }: LoginButtonProps) {
    return (
        <button className={buttonVariants({ provider })} onClick={onClick}>
            <img src={image} alt={`${label} logo`} className="h-9 w-9 shrink-0 rounded-[10px] object-cover" />
            <span className={labelVariants({ provider })}>{label} 계정으로 로그인</span>
        </button>
    )
}

export default LoginButton
