import { type ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useEscapeKey } from "@/hooks/useEscapeKey";
import { useFocusTrap } from "@/hooks/useFocusTrap";

interface ModalProps {
    title: string
    // 제목 위에 놓는 보조 영역. 예: 유형 아이콘과 라벨
    eyebrow?: ReactNode
    onClose: () => void
    // 상단 닫기 버튼의 접근 가능한 이름. 본문에 "닫기" 버튼이 따로 있을 때 겹치지 않게 바꾼다.
    closeLabel?: string
    // 하단 버튼 영역. 없으면 그리지 않는다.
    footer?: ReactNode
    children: ReactNode
}

/** 화면 위에 띄우는 대화상자. 렌더하는 동안 열려 있고, 닫으려면 부모가 렌더를 멈춘다. */
function Modal({ title, eyebrow, onClose, closeLabel = "닫기", footer, children }: ModalProps) {
    const titleId = useId();
    const dialogRef = useRef<HTMLDivElement>(null);

    useEscapeKey(true, onClose);
    useBodyScrollLock(true);
    useFocusTrap(true, [dialogRef]);

    useEffect(() => {
        const previouslyFocusedElement = document.activeElement as HTMLElement | null;
        dialogRef.current?.focus();
        return () => {
            previouslyFocusedElement?.focus();
        };
    }, []);

    // 뒤에 가려진 페이지 콘텐츠가 Tab으로 접근되지 않도록 비활성화한다.
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
                    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                        {eyebrow}
                        <h2 id={titleId} className="text-lg leading-6.5 font-bold text-black md:text-xl md:leading-7">{title}</h2>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label={closeLabel}
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
