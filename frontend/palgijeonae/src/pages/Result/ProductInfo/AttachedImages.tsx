import { type ReactEventHandler, useState } from "react";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import ImageLightbox from "@/components/common/ImageLightbox";
import SectionIntro from "@/components/common/SectionIntro";

interface AttachedImagesProps {
    imageUrls: string[]
}

// 이미지 로드에 실패하면 기본 썸네일로 대체한다. 기본 썸네일 자체가 실패해도 다시 시도하지 않도록 핸들러를 끊는다.
const handleImageError: ReactEventHandler<HTMLImageElement> = (event) => {
    event.currentTarget.onerror = null;
    event.currentTarget.src = defaultThumbnail;
};

function AttachedImages({ imageUrls }: AttachedImagesProps) {
    const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

    if (imageUrls.length === 0) {
        return null;
    }

    const lightboxImages = imageUrls.map((imageUrl, index) => ({ src: imageUrl, alt: `상세 이미지 ${index + 1}` }));

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <SectionIntro title="첨부된 이미지" size="xl"/>
            <div className="flex w-full items-start gap-3 overflow-x-auto">
                {imageUrls.map((imageUrl, index) => (
                    <button
                        key={imageUrl}
                        type="button"
                        onClick={() => setSelectedIndex(index)}
                        aria-label={`상세 이미지 ${index + 1} 크게 보기`}
                        className="relative h-50 w-50 shrink-0 cursor-pointer overflow-hidden rounded-xl bg-gray-100"
                    >
                        <img
                            src={imageUrl}
                            alt=""
                            onError={handleImageError}
                            className="h-full w-full object-cover"
                        />
                        <div className="absolute inset-x-0 bottom-0 bg-black/60 px-3.5 py-2.5">
                            <span className="text-sm text-white">상세 이미지 {index + 1}</span>
                        </div>
                    </button>
                ))}
            </div>
            {selectedIndex !== null && (
                <ImageLightbox
                    images={lightboxImages}
                    currentIndex={selectedIndex}
                    onIndexChange={setSelectedIndex}
                    onClose={() => setSelectedIndex(null)}
                />
            )}
        </div>
    );
}

export default AttachedImages;
