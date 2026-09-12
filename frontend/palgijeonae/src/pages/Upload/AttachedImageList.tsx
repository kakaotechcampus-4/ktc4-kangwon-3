import { useEffect, useMemo, useState } from "react";

import deleteIcon from "../../assets/delete-gray.svg";
import ImageLightbox from "./ImageLightbox.tsx";

interface AttachedImageListProps {
    title: string
    files: File[]
    onRemove: (index: number) => void
}

const DEFAULT_VISIBLE_COUNT = 8;

function AttachedImageList({ title, files, onRemove }: AttachedImageListProps) {
    const [expanded, setExpanded] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
    const previewUrls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);

    useEffect(() => {
        return () => {
            previewUrls.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [previewUrls]);

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
                        <div key={`${file.name}-${index}`} className="relative h-39 w-39">
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
