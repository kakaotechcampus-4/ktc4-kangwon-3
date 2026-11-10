import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useEscapeKey } from "@/hooks/useEscapeKey";
import { useFocusTrap } from "@/hooks/useFocusTrap";

interface ModalProps {
    title: string
    onClose: () => void
    // 하단 버튼 영역. 없으면 그리지 않는다.
    footer?: ReactNode
    children: ReactNode
}

/** 화면 위에 띄우는 대화상자. 렌더하는 동안 열려 있고, 닫으려면 부모가 렌더를 멈춘다. */
function Modal({ title, onClose, footer, children }: ModalProps) {
    const titleId = useId();
    const dialogRef = useRef<HTMLDivElement>(null);

    useEscapeKey(true, onClose);
    useBodyScrollLock(true);
    useFocusTrap(true, [dialogRef]);

    // 열리기 전에 포커스가 있던 요소. 안쪽 요소가 먼저 포커스를 가져가도 달라지지 않게 첫 렌더에서 잡아 둔다.
    const [previouslyFocusedElement] = useState(() => document.activeElement as HTMLElement | null);

    // 뒤에 가려진 페이지 콘텐츠가 Tab으로 접근되지 않도록 비활성화한다.
    // 닫을 때는 이 정리가 아래의 포커스 복귀보다 먼저 일어나야 한다. (inert 안의 요소는 포커스를 받지 못한다)
    useEffect(() => {
        const root = document.getElementById("root");
        if (!root) {
            return;
        }
        root.inert = true;
        return () => {
            root.inert = false;
        };
    }, []);

    useEffect(() => {
        // 안쪽 요소가 이미 포커스를 가져갔으면(예: 특정 썸네일) 그대로 둔다.
        if (!dialogRef.current?.contains(document.activeElement)) {
            dialogRef.current?.focus();
        }
        return () => {
            previouslyFocusedElement?.focus();
        };
    }, [previouslyFocusedElement]);

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-5" onClick={onClose}>
            <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                tabIndex={-1}
                className="flex max-h-full w-full max-w-140 flex-col rounded-2xl bg-white shadow-box outline-none"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="flex items-start gap-3 border-b border-neutral-line px-5 pt-5 pb-4 md:px-7 md:pt-7">
                    <h2 id={titleId} className="min-w-0 flex-1 text-lg leading-6.5 font-bold text-black md:text-xl md:leading-7">{title}</h2>
                    {/* 하단 버튼 영역에 "닫기" 버튼을 둘 수 있어서, 위 닫기 버튼은 이름을 다르게 한다. */}
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="창 닫기"
                        className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-neutral-border transition-colors duration-150 outline-none hover:bg-button-hover-bg focus-visible:ring-3 focus-visible:ring-primary/25"
                    >
                        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                        </svg>
                    </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 md:px-7">{children}</div>
                {footer && <div className="flex justify-end gap-2 px-5 pb-5 md:px-7 md:pb-7">{footer}</div>}
            </div>
        </div>,
        document.body,
    );
}

export default Modal;
