import {
    autoUpdate,
    flip,
    FloatingPortal,
    offset,
    shift,
    useDismiss,
    useFloating,
    useFocus,
    useHover,
    useInteractions,
    useRole,
} from "@floating-ui/react";
import { type ReactNode, useId, useState } from "react";

import { cn } from "@/lib/cn";

interface HelpTooltipProps {
    // 트리거 버튼의 스크린리더용 설명. 화면에는 "?"만 보인다.
    label: string
    // 툴팁 내용. 여러 줄이 필요하면 ReactNode로 구성한다.
    children: ReactNode
    // 툴팁 너비/줄바꿈을 맞출 때 사용.
    className?: string
}

/**
 * "?" 버튼에 커서를 올리거나 포커스하면 안내 문구를 보여주는 공용 툴팁.
 * 화면 가장자리에 가까우면 floating-ui가 반대쪽으로 자동으로 뒤집어 잘리지 않게 한다.
 */
function HelpTooltip({ label, children, className }: HelpTooltipProps) {
    const tooltipId = useId();
    const [isOpen, setIsOpen] = useState(false);

    const { refs, floatingStyles, context } = useFloating({
        open: isOpen,
        onOpenChange: setIsOpen,
        placement: "top",
        middleware: [offset(8), flip(), shift({ padding: 8 })],
        whileElementsMounted: autoUpdate,
    });

    const { getReferenceProps, getFloatingProps } = useInteractions([
        useHover(context),
        useFocus(context),
        useDismiss(context),
        useRole(context, { role: "tooltip" }),
    ]);

    return (
        <>
            <button
                ref={(node) => refs.setReference(node)}
                {...getReferenceProps()}
                type="button"
                aria-label={label}
                aria-describedby={tooltipId}
                className="flex h-5 w-5 shrink-0 cursor-help items-center justify-center rounded-full border border-field-line bg-white text-xs leading-none font-medium text-neutral-dark transition-colors duration-150 outline-none hover:bg-button-hover-bg focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/25"
            >
                ?
            </button>
            {isOpen && (
                <FloatingPortal>
                    <div
                        ref={(node) => refs.setFloating(node)}
                        id={tooltipId}
                        style={floatingStyles}
                        {...getFloatingProps()}
                        className={cn(
                            "pointer-events-none z-50 flex w-max max-w-xs flex-col gap-1 whitespace-pre-line rounded-lg bg-neutral-dark px-4 py-3 text-sm text-white shadow-lg",
                            className,
                        )}
                    >
                        {children}
                    </div>
                </FloatingPortal>
            )}
        </>
    );
}

export default HelpTooltip;
