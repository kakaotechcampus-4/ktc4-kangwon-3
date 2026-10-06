import { useMemo, useState } from "react";

import Button from "@/components/common/Button/index.tsx";

import { MAX_PRODUCT_IMAGE_COUNT, MAX_PRODUCT_NAME_LENGTH } from "./constraints.ts";
import AttachedImageList from "./form/AttachedImageList.tsx";
import FormField from "./form/FormField.tsx";
import ImageUploadField from "./form/ImageUploadField.tsx";
import type { Product } from "./types.ts";
import { validateProduct } from "./validation.ts";

interface InputFormProps {
    type: 'text/image' | 'url'
    onAdd: (product: Product) => void
}

// 입력 방식별 안내 문구
const HELP_CONTENT: Record<InputFormProps["type"], { text: string; tooltip: string }> = {
    "url": {
        text: "상세정보가 포함된 판매할 제품의 링크를 첨부하세요.",
        tooltip: "일부 링크는 AI가 접근하기 어려울 수 있습니다. 실패 시 텍스트 / 이미지 입력을 사용해주세요.",
    },
    "text/image": {
        text: "상세페이지를 텍스트나 이미지로 입력하세요. 둘 다 입력할 수도 있습니다.",
        tooltip: "분석을 위해 필요한 정보가 상세페이지에 충분히 포함되어 있는지 확인하세요.",
    },
};

function InputForm({ type, onAdd }: InputFormProps) {
    const [productName, setProductName] = useState("");
    const [productContent, setProductContent] = useState("");
    const [productImages, setProductImages] = useState<File[]>([]);
    const [link, setLink] = useState("");
    const [image, setImage] = useState<File | null>(null);
    // image가 바뀔 때만 새 배열을 만들어야 AttachedImageList의 useEffect가 불필요하게 재실행되지 않는다.
    const imageFiles = useMemo(() => (image ? [image] : []), [image]);

    const { text: helpText, tooltip: helpTooltip } = HELP_CONTENT[type];

    const handleAddProduct = () => {
        const candidate: Product = {
            id: crypto.randomUUID(),
            type,
            title: productName.trim(),
            productImageFile: image ?? undefined,
            // TODO: type이 3개 이상으로 늘어나면 Record<타입, () => Partial<Product>> 룩업으로 교체한다.
            ...(type === "url"
                ? { link: link.trim() }
                : { content: productContent.trim(), images: productImages }),
        };

        const error = validateProduct(candidate);
        if (error) {
            alert(error);
            return;
        }

        onAdd(candidate);

        setProductName("");
        setImage(null);
        setLink("");
        setProductContent("");
        setProductImages([]);
    };

    return (
        <div className="flex w-full flex-col gap-6">
            <FormField
                id="product-name"
                title="제품명"
                placeholder="제품을 구분하기 위한 상품명이나 별명을 입력하세요."
                value={productName}
                onChange={setProductName}
                maxLength={MAX_PRODUCT_NAME_LENGTH}
            />
            {type === 'text/image' && (
                <>
                    <FormField
                        id="product-content"
                        title="제품 상세페이지 내용"
                        placeholder="제품의 상세페이지 정보가 포함된 웹 페이지 내용을 복사하여 입력하세요."
                        variant="textarea"
                        value={productContent}
                        onChange={setProductContent}
                    />
                    <ImageUploadField
                        id="product-content-images"
                        title="상세페이지 이미지"
                        description="상세 페이지를 캡처한 이미지를 첨부하세요."
                        multiple={true}
                        isOption={false}
                        countLabel={`${productImages.length}/${MAX_PRODUCT_IMAGE_COUNT}`}
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
                </>
            )}
            {type === 'url' && (
                <>
                    <FormField
                        id="product-link"
                        title="제품 상세페이지 링크"
                        placeholder="https://...... 상품의 상세 정보가 담긴 상품 페이지 링크를 업로드 하세요."
                        value={link}
                        onChange={setLink}
                    />
                </>
            )}
            <ImageUploadField
                id="product-image"
                title="제품 대표 사진"
                description="제품을 구분할 대표 사진을 첨부하세요."
                isOption={true}
                onChange={(files) => setImage(files[0] ?? null)}
            />
            <AttachedImageList
                title="첨부된 제품 대표 사진"
                files={imageFiles}
                onRemove={() => setImage(null)}
            />
            <div className="flex w-full items-center justify-between gap-4">
                <div className="group relative flex min-w-0 items-center gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-neutral-border text-xs font-medium text-neutral-border">
                        ?
                    </span>
                    <p className="truncate text-sm text-neutral-dark">
                        {helpText}
                    </p>
                    <div className="pointer-events-none absolute bottom-full left-0 z-50 mb-2 hidden w-max whitespace-nowrap rounded-lg bg-neutral-dark px-3 py-2 text-sm text-white shadow-lg group-hover:block">
                        {helpTooltip}
                    </div>
                </div>
                <div className="shrink-0">
                    <Button text="상품 추가하기" onClick={handleAddProduct} fontSize={15} />
                </div>
            </div>
        </div>
    );
}

export default InputForm;
