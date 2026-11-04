import { cn } from "@/lib/cn";

interface PreviewIndicatorSlide {
    key: string
    label: string
}

interface PreviewIndicatorProps {
    slides: PreviewIndicatorSlide[]
    index: number
    onGoTo: (index: number) => void
    onCurrentSlideEnd: () => void
    prefersReducedMotion: boolean
    isPaused: boolean
    onTogglePause: () => void
}

/** 캐러셀 상단의 4구간 진행 바 + 라벨 + 일시정지 버튼. 현재 구간 바가 다 채워지면 onCurrentSlideEnd로 다음 슬라이드로 넘어간다. */
function PreviewIndicator({
    slides,
    index,
    onGoTo,
    onCurrentSlideEnd,
    prefersReducedMotion,
    isPaused,
    onTogglePause,
}: PreviewIndicatorProps) {
    return (
        <div className="flex w-full items-center gap-3 border-b border-neutral-border bg-white px-5 py-4">
            <div className="grid flex-1 grid-cols-2 gap-2 md:grid-cols-4">
                {slides.map((slide, slideIndex) => {
                    const isDone = slideIndex < index;
                    const isCurrent = slideIndex === index;

                    return (
                        <button
                            key={slide.key}
                            type="button"
                            onClick={() => onGoTo(slideIndex)}
                            aria-current={isCurrent ? "true" : undefined}
                            className={cn(
                                "flex cursor-pointer flex-col items-start gap-2 text-left text-sm",
                                isCurrent ? "font-bold text-primary" : "text-neutral-border",
                            )}
                        >
                            <span className="block h-1.5 w-full overflow-hidden rounded-full bg-neutral-border/20">
                                {/* index가 바뀔 때마다 key로 다시 마운트해서, 같은 구간이 두 번째로 "현재"가 돼도 애니메이션이 처음부터 재생되게 한다. */}
                                <span
                                    key={index}
                                    onAnimationEnd={isCurrent ? onCurrentSlideEnd : undefined}
                                    style={isCurrent ? { animationPlayState: isPaused ? "paused" : "running" } : undefined}
                                    className={cn(
                                        "block h-full bg-primary",
                                        isDone && "w-full",
                                        isCurrent && (prefersReducedMotion ? "w-full" : "w-0 motion-safe:animate-preview-progress"),
                                        !isDone && !isCurrent && "w-0",
                                    )}
                                />
                            </span>
                            {`${slideIndex + 1}. ${slide.label}`}
                        </button>
                    );
                })}
            </div>
            <button
                type="button"
                onClick={onTogglePause}
                aria-label={isPaused ? "자동 전환 다시 시작" : "자동 전환 멈춤"}
                className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border border-neutral-border text-neutral-text hover:border-primary hover:text-primary"
            >
                {isPaused ? (
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
                        <path d="M6 4l14 8-14 8V4z" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
                        <rect x="5" y="4" width="5" height="16" rx="1" />
                        <rect x="14" y="4" width="5" height="16" rx="1" />
                    </svg>
                )}
            </button>
        </div>
    );
}

export default PreviewIndicator;
