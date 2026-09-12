import { useState } from "react";

import FormField from "./FormField.tsx";
import ImageUploadField from "./ImageUploadField.tsx";
import AttachedImageList from "./AttachedImageList.tsx";
import Button from "../../components/common/Button/index.tsx";

const MAX_PRODUCT_IMAGE_COUNT = 20;

function TextImageInputForm() {
    const [productName, setProductName] = useState("");
    const [productContent, setProductContent] = useState("");
    const [productImages, setProductImages] = useState<File[]>([]);
    const [image, setImage] = useState<File | null>(null);

    return (
        <div className="flex w-full flex-col gap-6">
            <FormField
                id="product-name"
                title="제품명"
                placeholder="제품을 구분하기 위한 상품명이나 별명을 입력하세요."
                value={productName}
                onChange={setProductName}
            />
            <FormField
                id="product-content"
                title="제품 상세페이지 내용"
                placeholder="제품의 상세페이지 정보가 포함된 웹 페이지 내용을 복사하여 입력하세요."
                value={productContent}
                onChange={setProductContent}
            />
            <ImageUploadField
                id="product-content-images"
                title="상세페이지 이미지"
                description="상세 페이지를 캡처한 이미지를 첨부하세요."
                multiple={true}
                isOption={false}
                onChange={(newFiles) => {
                    const availableSlots = Math.max(MAX_PRODUCT_IMAGE_COUNT - productImages.length, 0);
                    if (newFiles.length > availableSlots) {
                        alert(`이미지는 최대 ${MAX_PRODUCT_IMAGE_COUNT}장까지 첨부할 수 있습니다. ${newFiles.length - availableSlots}장은 추가되지 않았습니다.`);
                    }
                    setProductImages((prev) => [...prev, ...newFiles.slice(0, availableSlots)]);
                }}
            />
            <AttachedImageList
                title="첨부된 상세페이지 이미지"
                files={productImages}
                onRemove={(index) => setProductImages((prev) => prev.filter((_, i) => i !== index))}
            />
            <ImageUploadField
                id="product-image"
                title="제품 대표 사진"
                description="제품을 구분할 대표 사진을 첨부하세요."
                isOption={true}
                onChange={(files) => setImage(files[0] ?? null)}
            />
            <AttachedImageList
                title="첨부된 제품 대표 사진"
                files={image ? [image] : []}
                onRemove={() => setImage(null)}
            />
            <div className="flex w-full items-center justify-between gap-4">
                <div className="group relative flex min-w-0 items-center gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-neutral-border text-xs font-medium text-neutral-border">
                        ?
                    </span>
                    <p className="truncate text-sm text-neutral-dark">
                        상세페이지를 텍스트나 이미지로 입력하세요. 둘 다 입력할 수도 있습니다.
                    </p>
                    <div className="pointer-events-none absolute bottom-full left-0 z-50 mb-2 hidden w-max whitespace-nowrap rounded-lg bg-neutral-dark px-3 py-2 text-sm text-white shadow-lg group-hover:block">
                        분석을 위해 필요한 정보가 상세페이지에 충분히 포함되어 있는지 확인하세요.
                    </div>
                </div>
                <div className="shrink-0">
                    <Button text="상품 추가하기" onClick={() => {}} fontSize={15} />
                </div>
            </div>
        </div>
     );
}

export default TextImageInputForm;
