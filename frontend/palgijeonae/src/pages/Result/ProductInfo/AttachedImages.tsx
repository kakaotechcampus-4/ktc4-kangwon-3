import type { ReactEventHandler } from "react";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";

interface AttachedImagesProps {
    imageUrls: string[]
}

// 이미지 로드에 실패하면 기본 썸네일로 대체한다. 기본 썸네일 자체가 실패해도 다시 시도하지 않도록 핸들러를 끊는다.
const handleImageError: ReactEventHandler<HTMLImageElement> = (event) => {
    event.currentTarget.onerror = null;
    event.currentTarget.src = defaultThumbnail;
};

function AttachedImages({ imageUrls }: AttachedImagesProps) {
    if (imageUrls.length === 0) {
        return null;
    }

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <h3 className="text-lg leading-tight font-bold text-black">첨부 이미지 {imageUrls.length}장</h3>
            <div className="flex w-full items-start gap-3 overflow-x-auto">
                {imageUrls.map((imageUrl, index) => (
                    <div key={imageUrl} className="relative h-50 w-50 shrink-0 overflow-hidden rounded-xl bg-gray-100">
                        <img
                            src={imageUrl}
                            alt={`상세 이미지 ${index + 1}`}
                            onError={handleImageError}
                            className="h-full w-full object-cover"
                        />
                        <div className="absolute inset-x-0 bottom-0 bg-black/60 px-3.5 py-2.5">
                            <span className="text-sm text-white">상세 이미지 {index + 1}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default AttachedImages;
