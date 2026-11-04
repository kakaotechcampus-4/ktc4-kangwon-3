import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
    "flex cursor-pointer items-center justify-center gap-2.5 self-start rounded-[10px] leading-[1.2] text-center disabled:cursor-default disabled:opacity-35 aria-disabled:cursor-default aria-disabled:opacity-35",
    {
        variants: {
            variant: {
                // 핵심 액션
                primary: "bg-primary px-[25px] py-[14px] font-bold text-white",
                // 보조 액션
                secondary: "border border-neutral-border bg-white px-[24px] py-[13px] font-semibold text-neutral-text enabled:hover:border-neutral-dark",
            },
        },
        defaultVariants: {
            variant: "primary",
        },
    },
);

interface ButtonProps extends VariantProps<typeof buttonVariants> {
    text: string
    onClick: () => void
    fontSize?: number
    disabled?: boolean
    // disabled와 달리 클릭은 막지 않는다 — 클릭 가능 사유를 안내해야 할 때 onClick 쪽에서 막는다.
    ariaDisabled?: boolean
    ariaDescribedBy?: string
}

function Button({ text, onClick, fontSize = 20, variant, disabled = false, ariaDisabled, ariaDescribedBy }: ButtonProps) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            aria-disabled={ariaDisabled || undefined}
            aria-describedby={ariaDescribedBy}
            className={cn(buttonVariants({ variant }))}
            style={{ fontSize: `${fontSize}px` }}
        >
            {text}
        </button>
    );
}

export default Button;
