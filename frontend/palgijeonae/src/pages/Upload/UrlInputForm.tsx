import { useState } from "react";

import FormField from "./FormField.tsx";
import ImageUploadField from "./ImageUploadField.tsx";

function UrlInputForm() {
    const [productName, setProductName] = useState("");
    const [link, setLink] = useState("");
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
                id="product-link"
                title="제품 상세페이지 링크"
                placeholder="https://...... 상품의 상세 정보가 담긴 상품 페이지 링크를 업로드 하세요."
                value={link}
                onChange={setLink}
            />
            <ImageUploadField
                id="product-image"
                title="제품 대표 사진"
                file={image}
                onChange={setImage}
            />
        </div>
    );
}

export default UrlInputForm;
