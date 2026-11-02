import { type ReactNode,useId } from "react";

import { cn } from "@/lib/cn";

interface HelpTooltipProps {
    // 트리거 버튼의 스크린리더용 설명. 화면에는 "?"만 보인다.
    label: string
    // 툴팁 내용. 여러 줄이 필요하면 ReactNode로 구성한다.
    children: ReactNode
    // 툴팁이 화면 밖으로 나가지 않도록 위치를 맞출 때 사용 (예: "right-0", "left-0").
    className?: string
}

/** "?" 버튼에 커서를 올리거나 포커스하면 안내 문구를 보여주는 공용 툴팁. */
function HelpTooltip({ label, children, className }: HelpTooltipProps) {
    const tooltipId = useId();

    return (
        <div className="group relative inline-flex shrink-0">
            <button
                type="button"
                aria-label={label}
                aria-describedby={tooltipId}
                className="flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-neutral-border text-xs leading-none font-medium text-neutral-border"
            >
                ?
            </button>
            <div
                id={tooltipId}
                role="tooltip"
                className={cn(
                    "pointer-events-none absolute bottom-full z-50 mb-2 hidden w-max max-w-xs flex-col gap-1 whitespace-pre-line rounded-lg bg-neutral-dark px-4 py-3 text-sm text-white shadow-lg group-hover:flex group-focus-within:flex",
                    className,
                )}
            >
                {children}
            </div>
        </div>
    );
}

export default HelpTooltip;
