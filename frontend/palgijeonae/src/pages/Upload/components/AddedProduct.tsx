import { useEffect, useState } from "react";

import { SourceType } from "@/api/types/common.ts"
import deleteIcon from "@/assets/delete-gray.svg"
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import imageIcon from "@/assets/upload-img_txt.svg"
import urlIcon from "@/assets/upload-url.svg"

interface AddedProductProps {
    type: SourceType;
    title: string;
    productImageFile?: File;
    onOpenDetail: () => void;
    onRemove: () => void;
}

function AddedProduct({ type, title, productImageFile, onOpenDetail, onRemove }: AddedProductProps) {
    const [thumbnail, setThumbnail] = useState<string | undefined>(undefined);

    // 자동으로 해제 되게끔 File을 받아와 useEffect 안에서 url을 생성한다.
    useEffect(() => {
        const url = productImageFile ? URL.createObjectURL(productImageFile) : undefined;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setThumbnail(url);
        return () => {
            if (url) {
                URL.revokeObjectURL(url);
            }
        };
    }, [productImageFile]);

    return (
        <div className="relative flex w-full items-center gap-3 rounded-xl border border-box-line bg-white p-3">
            <img src={thumbnail ? thumbnail : defaultThumbnail}
                alt="상품 썸네일"
                className="size-10 shrink-0 rounded-lg border border-box-line object-cover" />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-center gap-1">
                    <img src={type === SourceType.Url ? urlIcon : imageIcon}
                        alt=""
                        className="size-3.5" />
                    <p className="text-xs font-bold text-neutral-border">{type === SourceType.Url ? "URL" : "이미지 / 텍스트"}</p>
                </div>
                <h3 className="truncate text-sm font-bold text-neutral-dark">{title}</h3>
            </div>
            {/* 항목 전체를 누르는 영역. 삭제 버튼과 형제로 두어서 삭제 클릭이 항목 클릭으로 전달되지 않는다. */}
            <button
                type="button"
                onClick={onOpenDetail}
                aria-label={`${title} 자세히 보기`}
                aria-haspopup="dialog"
                title={title}
                className="absolute inset-0 cursor-pointer rounded-xl outline-none transition-colors duration-150 hover:bg-button-hover-bg/50 focus-visible:ring-3 focus-visible:ring-primary/25"
            />
            <button
                type="button"
                onClick={onRemove}
                aria-label="삭제"
                className="relative z-10 flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full outline-none transition-colors duration-150 hover:bg-button-active-bg focus-visible:ring-3 focus-visible:ring-primary/25"
            >
                <img src={deleteIcon} alt="" className="size-4" />
            </button>
        </div>
    );
}

export default AddedProduct;
