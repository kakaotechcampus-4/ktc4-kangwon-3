import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const defaultBoxVariants = cva(
    "box-border flex h-auto flex-col gap-5 rounded-xl border-box-line bg-white px-6 py-[18px]",
    {
        variants: {
            align: {
                left: "items-start text-left",
                right: "items-end text-right",
            },
            variant: {
                solid: "border border-solid",
                dashed: "border border-dashed border-box-dashed bg-transparent",
            },
            // 진단 결과 상태(배지, 태그, 경고 배너 공통)를 나타내는 박스 색 톤. index.css의 status 토큰과 연결된다.
            tone: {
                neutral: "",
                success: "border-status-success/40 bg-status-success-bg shadow-box-tone",
                warning: "border-status-warning/40 bg-status-warning-bg shadow-box-tone",
                danger: "border-status-danger/40 bg-status-danger-bg shadow-box-tone",
            },
            // tone과 달리 배경은 채우지 않고 테두리 색만 상태에 맞춘다.
            borderTone: {
                neutral: "",
                success: "border-status-success/60",
                warning: "border-status-warning/60",
                danger: "border-status-danger/60",
            },
        },
        compoundVariants: [
            { variant: "solid", tone: "neutral", class: "shadow-box" },
        ],
        defaultVariants: {
            align: "left",
            variant: "solid",
            tone: "neutral",
            borderTone: "neutral",
        },
    },
);

interface DefaultBoxProps extends VariantProps<typeof defaultBoxVariants> {
    width?: string
    className?: string
    children: ReactNode
}

function DefaultBox({ width = "full", align, variant, tone, borderTone, className, children }: DefaultBoxProps) {
    const widthClass = width === "full" ? "w-full" : width;

    return (
        <div className={cn(defaultBoxVariants({ align, variant, tone, borderTone }), widthClass, className)}>
            {children}
        </div>
    );
}

export default DefaultBox;
