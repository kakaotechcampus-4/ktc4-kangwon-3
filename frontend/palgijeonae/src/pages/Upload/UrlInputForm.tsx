import { useState } from "react";

import Button from "../../components/common/Button";
import FormField from "./FormField.tsx";
import ImageUploadField from "./ImageUploadField.tsx";
import AttachedImageList from "./AttachedImageList.tsx";

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
                        상세정보가 포함된 판매할 제품의 링크를 첨부하세요.
                    </p>
                    <div className="pointer-events-none absolute bottom-full left-0 z-50 mb-2 hidden w-max whitespace-nowrap rounded-lg bg-neutral-dark px-3 py-2 text-sm text-white shadow-lg group-hover:block">
                        일부 링크는 AI가 접근하기 어려울 수 있습니다. 실패 시 텍스트 / 이미지 입력을 사용해주세요.
                    </div>
                </div>
                <div className="shrink-0">
                    <Button text="상품 추가하기" onClick={() => {}} fontSize={15} />
                </div>
            </div>
        </div>
    );
}

export default UrlInputForm;
