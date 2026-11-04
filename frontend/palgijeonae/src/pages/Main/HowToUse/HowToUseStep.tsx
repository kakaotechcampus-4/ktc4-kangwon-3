import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface HowToUseStepProps {
    stepNumber: number
    isLast: boolean
    title: string
    tag?: string
    description: string
    tips: string[]
    preview: ReactNode
}

// 설명 문구의 "**글자**" 구간만 굵게 렌더링한다.
function renderDescription(description: string) {
    return description.split(/(\*\*[^*]+\*\*)/g).map((part, index) => (
        part.startsWith("**") && part.endsWith("**")
            ? <span key={index} className="font-semibold text-black">{part.slice(2, -2)}</span>
            : part
    ));
}

function HowToUseStep({ stepNumber, isLast, title, tag, description, tips, preview }: HowToUseStepProps) {
    return (
        <li className={cn("relative @container", !isLast && "pb-12")}>
            {!isLast && <span aria-hidden className="absolute top-9 bottom-0 -left-11 w-0.5 bg-primary" />}
            <span className="absolute -left-15 top-0 flex h-9 w-9 items-center justify-center rounded-full bg-primary text-base font-bold text-white">
                {stepNumber}
            </span>
            {/* 뷰포트가 아니라 이 영역이 실제로 받는 너비 기준으로 2단 여부를 판단한다 (main 폭이 줄면 뷰포트와 무관하게 좁아짐) */}
            <div className="grid grid-cols-1 items-start gap-7 @2xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                <div className="flex flex-col gap-2.5 pt-1">
                    <h3 className="flex flex-wrap items-center gap-2 text-xl font-semibold text-black">
                        {title}
                        {tag && (
                            <span className="rounded-full bg-status-warning-bg px-2.5 py-1 text-sm font-semibold text-status-warning">
                                {tag}
                            </span>
                        )}
                    </h3>
                    <p className="text-base leading-relaxed whitespace-pre-line text-neutral-text">
                        {renderDescription(description)}
                    </p>
                    <ul className="flex flex-col gap-1.5">
                        {tips.map((tip) => (
                            <li key={tip} className="flex items-start gap-2 text-base text-neutral-border">
                                <span className="mt-1.5 size-1.25 shrink-0 rounded-full bg-primary" />
                                {tip}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="rounded-2xl bg-neutral-border/5 p-3.5">
                    {preview}
                </div>
            </div>
        </li>
    );
}

export default HowToUseStep;
