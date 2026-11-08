import { type ReactNode,useRef } from "react";

import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/cn";

import { usePreviewScale } from "./usePreviewScale";

// 모바일 본문 폭(390px 화면 − 좌우 여백 20px×2)
const MOBILE_BASE_WIDTH = 350;

interface PreviewFrameProps {
    label: string
    children: ReactNode
    className?: string
    baseWidth: number
    maxHeight?: number
    // 모바일(768px 미만)에서는 모바일 화면 폭 기준으로 그린 뒤 줄인다. 데스크톱 기준 폭으로 펼치면 모바일 레이아웃이 너무 작게 줄어든다.
    mobileBaseWidth?: number
    mobileMaxHeight?: number
}

/**
 * 실제 페이지 컴포넌트를 정적 미리보기로 보여줄 때 쓰는 공용 래퍼.
 * 콘텐츠를 baseWidth(모바일은 mobileBaseWidth) 기준 원래 너비로 렌더링한 뒤, 담긴 공간의 너비에 맞춰 자동으로 축소한다(확대는 하지 않음).
 * inert로 클릭·포커스를 막는다.
 */
function PreviewFrame({ label, children, className, baseWidth, maxHeight, mobileBaseWidth = MOBILE_BASE_WIDTH, mobileMaxHeight }: PreviewFrameProps) {
    const figureRef = useRef<HTMLElement>(null);
    const isMobile = useIsMobile();
    const activeBaseWidth = isMobile ? mobileBaseWidth : baseWidth;
    const activeMaxHeight = isMobile ? (mobileMaxHeight ?? maxHeight) : maxHeight;
    const scale = usePreviewScale(figureRef, activeBaseWidth);

    return (
        <figure
            ref={figureRef}
            aria-label={label}
            className={cn("m-0", activeMaxHeight && "relative overflow-hidden", className)}
            style={activeMaxHeight ? { maxHeight: activeMaxHeight } : undefined}
        >
            <div inert className="mx-auto select-none" style={{ width: activeBaseWidth, zoom: scale }}>
                {children}
            </div>
        </figure>
    );
}

export default PreviewFrame;
