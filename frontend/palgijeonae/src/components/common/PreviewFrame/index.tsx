import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface PreviewFrameProps {
    label: string
    children: ReactNode
    className?: string
    zoom?: number
}

/** 실제 페이지 컴포넌트를 정적 미리보기로 보여줄 때 쓰는 공용 래퍼. inert로 클릭·포커스를 막는다. */
function PreviewFrame({ label, children, className, zoom = 0.85 }: PreviewFrameProps) {
    return (
        <figure aria-label={label} className={cn(className)}>
            <div inert className="select-none" style={{ zoom }}>
                {children}
            </div>
        </figure>
    );
}

export default PreviewFrame;
