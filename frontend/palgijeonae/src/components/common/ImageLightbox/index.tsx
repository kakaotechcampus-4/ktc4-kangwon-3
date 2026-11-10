import { useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import deleteIcon from "@/assets/delete-gray.svg";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { cn } from "@/lib/cn";

export interface LightboxImage {
    src: string
    alt: string
}

interface ImageLightboxProps {
    images: LightboxImage[]
    currentIndex: number
    onIndexChange: (index: number) => void
    onClose: () => void
    // 없으면 삭제(X) 버튼을 보여주지 않는다. 
    onRemove?: (index: number) => void
}

function ImageLightbox({ images, currentIndex, onIndexChange, onClose, onRemove }: ImageLightboxProps) {
    const dialogRef = useRef<HTMLDivElement>(null);

    const goToPrev = useCallback(() => {
        onIndexChange((currentIndex - 1 + images.length) % images.length);
    }, [currentIndex, images.length, onIndexChange]);

    const goToNext = useCallback(() => {
        onIndexChange((currentIndex + 1) % images.length);
    }, [currentIndex, images.length, onIndexChange]);

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

    useBodyScrollLock(true);

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
        const previouslyFocusedElement = document.activeElement as HTMLElement | null;
        dialogRef.current?.focus();
        return () => {
            previouslyFocusedElement?.focus();
        };
    }, []);

    const currentImage = images[currentIndex];
    if (!currentImage) {
        return null;
    }

    return createPortal(
        <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="이미지 미리보기"
            tabIndex={-1}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-black/40 p-4 md:p-6"
            onClick={onClose}
        >
            <button
                type="button"
                onClick={onClose}
                aria-label="닫기"
                className="absolute top-3 right-3 z-10 flex h-10 w-10 md:top-6 md:right-6 cursor-pointer items-center justify-center rounded-full bg-white shadow"
            >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                </svg>
            </button>

            <div
                className="relative flex w-full min-h-0 max-w-240 flex-1 items-center justify-center"
                onClick={(event) => event.stopPropagation()}
            >
                {images.length > 1 && (
                    <button
                        type="button"
                        onClick={goToPrev}
                        aria-label="이전 이미지"
                        className="absolute left-0 z-10 flex h-10 w-10 cursor-pointer md:h-12 md:w-12 items-center justify-center rounded-full bg-white shadow"
                    >
                        <svg viewBox="0 0 24 24" className="h-5 w-5 md:h-6 md:w-6" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                )}

                <div className="relative min-h-0 min-w-0 max-h-full max-w-full shadow-xl">
                    <img
                        src={currentImage.src}
                        alt={currentImage.alt}
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

                {images.length > 1 && (
                    <button
                        type="button"
                        onClick={goToNext}
                        aria-label="다음 이미지"
                        className="absolute right-0 z-10 flex h-10 w-10 cursor-pointer md:h-12 md:w-12 items-center justify-center rounded-full bg-white shadow"
                    >
                        <svg viewBox="0 0 24 24" className="h-5 w-5 md:h-6 md:w-6" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                )}
            </div>

            {images.length > 1 && (
                <div
                    className="flex w-full max-w-240 gap-3 overflow-x-auto px-4 md:px-6"
                    onClick={(event) => event.stopPropagation()}
                >
                    {images.map((image, index) => (
                        <button
                            key={index}
                            type="button"
                            onClick={() => onIndexChange(index)}
                            aria-current={index === currentIndex ? "true" : undefined}
                            className={cn(
                                "h-16 w-16 shrink-0 overflow-hidden rounded-xl border-2",
                                index === currentIndex ? "border-primary" : "border-transparent",
                            )}
                        >
                            <img src={image.src} alt={image.alt} className="h-full w-full object-cover" />
                        </button>
                    ))}
                </div>
            )}
        </div>,
        document.body,
    );
}

export default ImageLightbox;
