import { type ReactNode,useRef } from "react";

import { cn } from "@/lib/cn";

import { usePreviewScale } from "./usePreviewScale";

interface PreviewFrameProps {
    label: string
    children: ReactNode
    className?: string
    baseWidth: number
    maxHeight?: number
}

/**
 * 실제 페이지 컴포넌트를 정적 미리보기로 보여줄 때 쓰는 공용 래퍼.
 * 콘텐츠를 baseWidth 기준 원래 너비로 렌더링한 뒤, 담긴 공간의 너비에 맞춰 자동으로 축소한다(확대는 하지 않음).
 * inert로 클릭·포커스를 막는다.
 */
function PreviewFrame({ label, children, className, baseWidth, maxHeight }: PreviewFrameProps) {
    const figureRef = useRef<HTMLElement>(null);
    const scale = usePreviewScale(figureRef, baseWidth);

    return (
        <figure
            ref={figureRef}
            aria-label={label}
            className={cn(maxHeight && "relative overflow-hidden", className)}
            style={maxHeight ? { maxHeight } : undefined}
        >
            <div inert className="select-none" style={{ width: baseWidth, zoom: scale }}>
                {children}
            </div>
            {maxHeight && (
                <div
                    aria-hidden
                    className="pointer-events-none absolute right-0 bottom-0 left-0 h-16 bg-gradient-to-t from-white to-transparent"
                />
            )}
        </figure>
    );
}

export default PreviewFrame;
