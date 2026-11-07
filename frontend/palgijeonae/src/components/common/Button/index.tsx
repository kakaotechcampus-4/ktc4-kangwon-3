import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
    // disabled는 variant별 전용 색을 쓰고, aria-disabled는 원래 색을 유지한 채 투명도만 낮춘다.
    "flex cursor-pointer items-center justify-center gap-2.5 self-start rounded-xl leading-[1.2] text-center transition-[background-color,border-color,box-shadow] duration-150 outline-none focus-visible:ring-3 focus-visible:ring-primary/25 disabled:cursor-default aria-disabled:cursor-default aria-disabled:opacity-35",
    {
        variants: {
            variant: {
                // 핵심 액션
                primary:
                    "bg-primary px-6.25 py-3.5 font-bold text-white shadow-button-primary enabled:not-aria-disabled:hover:bg-primary-hover enabled:not-aria-disabled:hover:shadow-button-primary-hover enabled:not-aria-disabled:active:bg-primary-active enabled:not-aria-disabled:active:shadow-none disabled:bg-button-disabled-bg disabled:text-button-disabled-text disabled:shadow-none",
                // 보조 액션
                secondary:
                    "border border-box-line bg-white px-6 py-3.25 font-semibold text-neutral-text shadow-button-secondary enabled:not-aria-disabled:hover:border-button-line-hover enabled:not-aria-disabled:hover:bg-button-hover-bg enabled:not-aria-disabled:active:bg-button-active-bg enabled:not-aria-disabled:active:shadow-none focus-visible:border-primary disabled:border-neutral-line disabled:bg-button-hover-bg disabled:text-button-disabled-text disabled:shadow-none",
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
