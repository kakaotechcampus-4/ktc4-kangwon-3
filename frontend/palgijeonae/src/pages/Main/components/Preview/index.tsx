import type { CSSProperties } from "react";

import SectionIntro from "@/components/common/SectionIntro";
import { cn } from "@/lib/cn";
import PreviewIndicator from "@/pages/Main/components/Preview/components/PreviewIndicator";
import { usePreviewCarousel } from "@/pages/Main/components/Preview/hooks/usePreviewCarousel";

import { PREVIEW_DURATION,PREVIEW_SLIDES } from "./constants";


/** 메인 페이지 서비스 미리보기 캐러셀. 4개 화면을 자동으로 넘겨가며 보여준다. */
function Preview() {
    const { index, goTo, next, prefersReducedMotion } = usePreviewCarousel(PREVIEW_SLIDES.length);
    const currentSlide = PREVIEW_SLIDES[index];

    return (
        <div
            className="w-full flex flex-col gap-8"
            style={{ "--preview-duration": PREVIEW_DURATION } as CSSProperties}
            aria-roledescription="carousel"
            aria-label="서비스 미리보기"
        >
            <SectionIntro title='"팔기전에" 사용 전 미리 보여 드려요' description="쉽고 간단하게 사용할 수 있어요. 자세한 사용 방법은 아래에서 확인하세요." size="2xl" />
            <div className="w-full overflow-hidden rounded-2xl border border-box-line bg-neutral-bg shadow-box">
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
