import { type RefObject,useLayoutEffect, useState } from "react";

/** 요소의 실제 너비를 측정해서 baseWidth 기준 콘텐츠를 얼마나 축소해야 할지 계산한다. 확대는 하지 않는다(최대 1). */
export function usePreviewScale(ref: RefObject<HTMLElement | null>, baseWidth: number) {
    const [scale, setScale] = useState(1);

    useLayoutEffect(() => {
        const element = ref.current;
        if (!element) {
            return;
        }

        const updateScale = (width: number) => {
            setScale(Math.min(1, width / baseWidth));
        };

        updateScale(element.getBoundingClientRect().width);

        const observer = new ResizeObserver(([entry]) => updateScale(entry.contentRect.width));
        observer.observe(element);
        return () => observer.disconnect();
    }, [ref, baseWidth]);

    return scale;
}
