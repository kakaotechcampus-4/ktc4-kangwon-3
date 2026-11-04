import { useState } from "react";

function getPrefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** 미리보기 캐러셀의 현재 인덱스·이동 함수, 일시정지 여부와 동작 줄이기 설정 여부를 관리한다. */
export function usePreviewCarousel(slideCount: number) {
    const [index, setIndex] = useState(0);
    // 설정은 마운트 시점 값으로 고정한다. 모킹 중 바뀔 일이 거의 없고, 바뀌어도 새로고침하면 반영된다.
    const [prefersReducedMotion] = useState(getPrefersReducedMotion);
    const [isPaused, setIsPaused] = useState(false);

    const goTo = (nextIndex: number) => {
        setIndex(((nextIndex % slideCount) + slideCount) % slideCount);
    };

    const next = () => goTo(index + 1);
    const prev = () => goTo(index - 1);
    const togglePause = () => setIsPaused((prev) => !prev);

    return { index, goTo, next, prev, prefersReducedMotion, isPaused, togglePause };
}
