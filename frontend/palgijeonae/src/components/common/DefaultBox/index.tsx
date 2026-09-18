import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const defaultBoxVariants = cva(
    "box-border flex h-auto flex-col gap-5 rounded-[10px] border-[#9d9d9d] px-6 py-[18px]",
    {
        variants: {
            align: {
                left: "items-start text-left",
                right: "items-end text-right",
            },
            variant: {
                solid: "border border-solid",
                dashed: "border border-dashed",
            },
        },
        defaultVariants: {
            align: "left",
            variant: "solid",
        },
    },
);

interface DefaultBoxProps extends VariantProps<typeof defaultBoxVariants> {
    width?: string
    className?: string
    children: ReactNode
}

function DefaultBox({ width = "full", align, variant, className, children }: DefaultBoxProps) {
    const widthClass = width === "full" ? "w-full" : width;

    return (
        <div className={cn(defaultBoxVariants({ align, variant }), widthClass, className)}>
            {children}
        </div>
    );
}

export default DefaultBox;
