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
            // 진단 결과 상태(배지, 태그, 경고 배너 공통)를 나타내는 박스 색 톤. index.css의 status 토큰과 연결된다.
            tone: {
                neutral: "",
                success: "border-status-success bg-status-success-bg",
                warning: "border-status-warning bg-status-warning-bg",
                danger: "border-status-danger bg-status-danger-bg",
            },
        },
        defaultVariants: {
            align: "left",
            variant: "solid",
            tone: "neutral",
        },
    },
);

interface DefaultBoxProps extends VariantProps<typeof defaultBoxVariants> {
    width?: string
    className?: string
    children: ReactNode
}

function DefaultBox({ width = "full", align, variant, tone, className, children }: DefaultBoxProps) {
    const widthClass = width === "full" ? "w-full" : width;

    return (
        <div className={cn(defaultBoxVariants({ align, variant, tone }), widthClass, className)}>
            {children}
        </div>
    );
}

export default DefaultBox;
