import type { CSSProperties } from "react";

import { cn } from "@/lib/cn";

import { PREVIEW_DURATION,PREVIEW_SLIDES } from "./constants";
import PreviewIndicator from "./PreviewIndicator";
import { usePreviewCarousel } from "./usePreviewCarousel";


/** 메인 페이지 서비스 미리보기 캐러셀. 4개 화면을 자동으로 넘겨가며 보여준다. */
function Preview() {
    const { index, goTo, next, prefersReducedMotion } = usePreviewCarousel(PREVIEW_SLIDES.length);
    const currentSlide = PREVIEW_SLIDES[index];

    return (
        <div
            className="w-full"
            style={{ "--preview-duration": PREVIEW_DURATION } as CSSProperties}
            aria-roledescription="carousel"
            aria-label="서비스 미리보기"
        >
            <div className="w-full overflow-hidden rounded-2xl border border-neutral-border bg-neutral-bg">
                <PreviewIndicator
                    slides={PREVIEW_SLIDES}
                    index={index}
                    onGoTo={goTo}
                    onCurrentSlideEnd={next}
                    prefersReducedMotion={prefersReducedMotion}
                />
                <div className="flex w-full flex-col gap-6 px-6 py-7">
                    <p className="text-center text-base font-medium text-neutral-text">{currentSlide.caption}</p>
                    <div className="grid w-full grid-cols-1">
                        {PREVIEW_SLIDES.map((slide, slideIndex) => {
                            const isActive = slideIndex === index;
                            return (
                                <div
                                    key={slide.key}
                                    className={cn(
                                        "col-start-1 row-start-1 overflow-hidden p-5 rounded-xl border-2 border-neutral-line bg-white transition-opacity duration-450",
                                        isActive ? "visible opacity-100" : "invisible opacity-0",
                                    )}
                                >
                                    <slide.Component />
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Preview;
