import { cva, type VariantProps } from "class-variance-authority";
import { useEffect, useRef, useState } from "react";

import deleteIcon from "@/assets/delete-gray.svg";
import ImageLightbox from "@/components/common/ImageLightbox";
import { cn } from "@/lib/cn";

const thumbnailVariants = cva("relative", {
    variants: {
        thumbnailSize: {
            lg: 'aspect-square w-full md:h-39 md:w-39',
            sm: 'h-16 w-16',
        },
    },
    defaultVariants: {
        thumbnailSize: 'lg',
    },
});

interface AttachedImageListProps extends VariantProps<typeof thumbnailVariants> {
    title: string
    files: File[]
    onRemove?: (index: number) => void
    // 있으면 썸네일을 눌러도 내부 확대 창을 띄우지 않고 이 함수로 알린다. 확대 창을 어디서 띄울지 부모가 정할 때 쓴다.
    onImageClick?: (index: number) => void
    // 이 순번의 썸네일에 처음부터 포커스를 둔다. 확대 창을 닫고 돌아왔을 때 누른 썸네일을 이어 가리키려고 쓴다.
    focusIndex?: number
}

const DEFAULT_VISIBLE_COUNT = 8;

function AttachedImageList({ title, files, onRemove, thumbnailSize, onImageClick, focusIndex }: AttachedImageListProps) {
    const [expanded, setExpanded] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
    const [previewUrls, setPreviewUrls] = useState<string[]>([]);
    const thumbnailButtons = useRef<(HTMLButtonElement | null)[]>([]);

    useEffect(() => {
        if (focusIndex !== undefined) {
            thumbnailButtons.current[focusIndex]?.focus();
        }
    }, [focusIndex]);

    useEffect(() => {
        const urls = files.map((file) => URL.createObjectURL(file));
        // 생성/해제를 같은 effect에 묶지 않으면 StrictMode 이중 실행 때 방금 만든 URL이 해제만 되고 재생성되지 않는다.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setPreviewUrls(urls);
        return () => {
            urls.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [files]);

    const clampedSelectedIndex = selectedIndex !== null && files.length > 0
        ? Math.min(selectedIndex, files.length - 1)
        : null;

    if (files.length === 0) {
        return null;
    }

    const hasOverflow = files.length > DEFAULT_VISIBLE_COUNT;
    const visibleCount = expanded ? files.length : Math.min(files.length, DEFAULT_VISIBLE_COUNT);
    const hiddenCount = files.length - visibleCount;
    const lightboxImages = files.map((file, index) => ({ src: previewUrls[index], alt: file.name }));

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center justify-between">
                <h3 className="text-base leading-6 font-semibold text-black md:text-xl">{title}</h3>
                {hasOverflow && (
                    <button
                        type="button"
                        onClick={() => setExpanded((prev) => !prev)}
                        aria-expanded={expanded}
                        className="cursor-pointer text-sm font-medium text-neutral-border"
                    >
                        {expanded ? "접기" : `모두 보기 (+${files.length - DEFAULT_VISIBLE_COUNT})`}
                    </button>
                )}
            </div>
            <div className={cn(thumbnailSize === "sm" ? "flex w-full flex-wrap gap-4" : "grid w-full grid-cols-3 gap-3 md:flex md:flex-wrap md:gap-4")}>
                {files.slice(0, visibleCount).map((file, index) => {
                    const isLastVisible = index === visibleCount - 1;
                    const showMoreOverlay = isLastVisible && hiddenCount > 0;

                    return (
                        <div key={`${file.name}-${index}`} className={thumbnailVariants({ thumbnailSize })}>
                            {showMoreOverlay ? (
                                <>
                                    <img
                                        src={previewUrls[index]}
                                        alt=""
                                        className="h-full w-full rounded-2xl object-cover"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setExpanded(true)}
                                        className="absolute inset-0 flex cursor-pointer items-center justify-center rounded-2xl bg-white/70 text-lg font-semibold text-black"
                                    >
                                        +{hiddenCount}
                                    </button>
                                </>
                            ) : (
                                <button
                                    type="button"
                                    ref={(node) => {
                                        thumbnailButtons.current[index] = node;
                                    }}
                                    onClick={() => (onImageClick ? onImageClick(index) : setSelectedIndex(index))}
                                    aria-label={`${file.name} 크게 보기`}
                                    className="h-full w-full cursor-pointer rounded-2xl"
                                >
                                    <img
                                        src={previewUrls[index]}
                                        alt=""
                                        className="h-full w-full rounded-2xl object-cover"
                                    />
                                </button>
                            )}
                            {!showMoreOverlay && onRemove && (
                                <button
                                    type="button"
                                    onClick={() => onRemove(index)}
                                    className="absolute top-2 right-2 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-white"
                                >
                                    <img src={deleteIcon} alt="삭제" className="h-full w-full" />
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
            {clampedSelectedIndex !== null && (
                <ImageLightbox
                    images={lightboxImages}
                    currentIndex={clampedSelectedIndex}
                    onIndexChange={setSelectedIndex}
                    onClose={() => setSelectedIndex(null)}
                    onRemove={onRemove}
                />
            )}
        </div>
    );
}

export default AttachedImageList;
