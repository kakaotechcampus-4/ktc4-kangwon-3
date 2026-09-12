import { useState } from "react";

import FormField from "./FormField.tsx";
import ImageUploadField from "./ImageUploadField.tsx";
import AttachedImageList from "./AttachedImageList.tsx";

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
                onChange={(newFiles) => setProductImages((prev) => [...prev, ...newFiles])}
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
        </div>
     );
}

export default TextImageInputForm;
