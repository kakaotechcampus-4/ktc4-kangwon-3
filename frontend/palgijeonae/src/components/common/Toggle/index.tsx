import { cva } from "class-variance-authority";

import { cn } from "@/lib/cn";

const trackVariants = cva("relative h-7 w-12 shrink-0 rounded-full transition-colors", {
    variants: {
        checked: {
            true: "bg-primary",
            false: "bg-neutral-border/40",
        },
    },
});

const knobVariants = cva("absolute top-1 left-1 h-5 w-5 rounded-full bg-white transition-transform", {
    variants: {
        checked: {
            true: "translate-x-5",
            false: "translate-x-0",
        },
    },
});

interface ToggleProps {
    checked: boolean
    onChange: (checked: boolean) => void
    disabled?: boolean
    className?: string
}

function Toggle({ checked, onChange, disabled, className }: ToggleProps) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            disabled={disabled}
            onClick={() => onChange(!checked)}
            className={cn(trackVariants({ checked }), disabled && "cursor-not-allowed opacity-50", className)}
        >
            <span className={knobVariants({ checked })} />
        </button>
    );
}

export default Toggle;
