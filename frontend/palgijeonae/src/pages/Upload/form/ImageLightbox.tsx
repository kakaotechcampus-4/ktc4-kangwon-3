import { useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import deleteIcon from "@/assets/delete-gray.svg";
import { cn } from "@/lib/cn";

interface ImageLightboxProps {
    files: File[]
    previewUrls: string[]
    currentIndex: number
    onIndexChange: (index: number) => void
    onClose: () => void
    onRemove?: (index: number) => void
}

function ImageLightbox({ files, previewUrls, currentIndex, onIndexChange, onClose, onRemove }: ImageLightboxProps) {
    const dialogRef = useRef<HTMLDivElement>(null);

    const goToPrev = useCallback(() => {
        onIndexChange((currentIndex - 1 + files.length) % files.length);
    }, [currentIndex, files.length, onIndexChange]);

    const goToNext = useCallback(() => {
        onIndexChange((currentIndex + 1) % files.length);
    }, [currentIndex, files.length, onIndexChange]);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "ArrowLeft") {
                goToPrev();
            } else if (event.key === "ArrowRight") {
                goToNext();
            } else if (event.key === "Escape") {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [goToPrev, goToNext, onClose]);

    useEffect(() => {
        const originalOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = originalOverflow;
        };
    }, []);

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

    const currentFile = files[currentIndex];
    if (!currentFile) {
        return null;
    }

    return createPortal(
        <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="이미지 미리보기"
            tabIndex={-1}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-white/20 p-6 backdrop-blur-xs"
            onClick={onClose}
        >
            <button
                type="button"
                onClick={onClose}
                className="absolute top-6 right-6 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full bg-white shadow"
            >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                </svg>
            </button>

            <div
                className="relative flex w-full min-h-0 max-w-240 flex-1 items-center justify-center"
                onClick={(event) => event.stopPropagation()}
            >
                {files.length > 1 && (
                    <button
                        type="button"
                        onClick={goToPrev}
                        className="absolute left-0 z-10 flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-white shadow"
                    >
                        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                )}

                <div className="relative min-h-0 min-w-0 max-h-full max-w-full shadow-xl">
                    <img
                        src={previewUrls[currentIndex]}
                        alt={currentFile.name}
                        className="max-h-[70vh] max-w-full object-contain shadow-lg"
                    />
                    {onRemove && (
                        <button
                            type="button"
                            onClick={() => onRemove(currentIndex)}
                            className="absolute top-3 right-3 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full bg-white"
                        >
                            <img src={deleteIcon} alt="삭제" className="h-full w-full" />
                        </button>
                    )}
                </div>

                {files.length > 1 && (
                    <button
                        type="button"
                        onClick={goToNext}
                        className="absolute right-0 z-10 flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-white shadow"
                    >
                        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                )}
            </div>

            {files.length > 1 && (
                <div
                    className="flex w-full max-w-240 gap-3 overflow-x-auto px-6"
                    onClick={(event) => event.stopPropagation()}
                >
                    {files.map((file, index) => (
                        <button
                            key={`${file.name}-${index}`}
                            type="button"
                            onClick={() => onIndexChange(index)}
                            className={cn(
                                "h-16 w-16 shrink-0 overflow-hidden rounded-xl border-2",
                                index === currentIndex ? "border-primary" : "border-transparent",
                            )}
                        >
                            <img src={previewUrls[index]} alt={file.name} className="h-full w-full object-cover" />
                        </button>
                    ))}
                </div>
            )}
        </div>,
        document.body,
    );
}

export default ImageLightbox;
