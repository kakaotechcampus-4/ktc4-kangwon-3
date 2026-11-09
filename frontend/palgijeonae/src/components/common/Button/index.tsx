import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

import { buttonVariants } from "./variants";

interface ButtonProps extends VariantProps<typeof buttonVariants> {
    text: string
    onClick: () => void
    fontSize?: number
    disabled?: boolean
    // disabled와 달리 클릭은 막지 않는다 — 클릭 가능 사유를 안내해야 할 때 onClick 쪽에서 막는다.
    ariaDisabled?: boolean
    ariaDescribedBy?: string
    className?: string
}

function Button({ text, onClick, fontSize = 20, variant, size, disabled = false, ariaDisabled, ariaDescribedBy, className }: ButtonProps) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            aria-disabled={ariaDisabled || undefined}
            aria-describedby={ariaDescribedBy}
            className={cn(buttonVariants({ variant, size }), className)}
            style={{ fontSize: `${fontSize}px` }}
        >
            {text}
        </button>
    );
}

export default Button;
