import { useEffect, useState } from "react";

import deleteIcon from "../../assets/delete-gray.svg";
import ImageLightbox from "./ImageLightbox.tsx";

interface AttachedImageListProps {
    title: string
    files: File[]
    onRemove?: (index: number) => void
    thumbnailSize?: 'lg' | 'sm'
}

const DEFAULT_VISIBLE_COUNT = 8;

const THUMBNAIL_SIZE_CLASSES: Record<NonNullable<AttachedImageListProps['thumbnailSize']>, string> = {
    lg: 'h-39 w-39',
    sm: 'h-16 w-16',
}

function AttachedImageList({ title, files, onRemove, thumbnailSize = 'lg' }: AttachedImageListProps) {
    const [expanded, setExpanded] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
    const [previewUrls, setPreviewUrls] = useState<string[]>([]);

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

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center justify-between">
                <h3 className="text-xl leading-6 font-semibold text-black">{title}</h3>
                {hasOverflow && (
                    <button
                        type="button"
                        onClick={() => setExpanded((prev) => !prev)}
                        className="cursor-pointer text-sm font-medium text-neutral-border"
                    >
                        {expanded ? "접기" : `모두 보기 (+${files.length - DEFAULT_VISIBLE_COUNT})`}
                    </button>
                )}
            </div>
            <div className="flex w-full flex-wrap gap-4">
                {files.slice(0, visibleCount).map((file, index) => {
                    const isLastVisible = index === visibleCount - 1;
                    const showMoreOverlay = isLastVisible && hiddenCount > 0;

                    return (
                        <div key={`${file.name}-${index}`} className={`relative ${THUMBNAIL_SIZE_CLASSES[thumbnailSize]}`}>
                            <img
                                src={previewUrls[index]}
                                alt={file.name}
                                onClick={() => setSelectedIndex(index)}
                                className="h-full w-full cursor-pointer rounded-2xl object-cover"
                            />
                            {showMoreOverlay ? (
                                <button
                                    type="button"
                                    onClick={() => setExpanded(true)}
                                    className="absolute inset-0 flex cursor-pointer items-center justify-center rounded-2xl bg-white/70 text-lg font-semibold text-black"
                                >
                                    +{hiddenCount}
                                </button>
                            ) : (
                                onRemove && (
                                    <button
                                        type="button"
                                        onClick={() => onRemove(index)}
                                        className="absolute top-2 right-2 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-white"
                                    >
                                        <img src={deleteIcon} alt="삭제" className="h-full w-full" />
                                    </button>
                                )
                            )}
                        </div>
                    );
                })}
            </div>
            {clampedSelectedIndex !== null && (
                <ImageLightbox
                    files={files}
                    previewUrls={previewUrls}
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
