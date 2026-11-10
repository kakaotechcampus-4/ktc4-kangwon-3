import { useMemo } from "react";

import { SourceType } from "@/api/types/common.ts"
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import imageIcon from "@/assets/upload-img_txt.svg"
import urlIcon from "@/assets/upload-url.svg"
import Button from "@/components/common/Button/index.tsx";
import Modal from "@/components/common/Modal/index.tsx";
import { isHttpUrl } from "@/lib/url";
import { useObjectUrls } from "@/pages/Upload/hooks/useObjectUrls.ts";
import type { Product } from "@/pages/Upload/types.ts";

import AttachedImageList from "./AttachedImageList.tsx";

const NO_FILES: File[] = [];

interface ProductDetailModalProps {
    product: Product
    onClose: () => void
    onRemove: () => void
    // 상세페이지 이미지 썸네일을 눌렀을 때. 확대 창은 부모가 띄운다.
    onImageClick: (index: number) => void
    // 확대 창을 닫고 돌아왔을 때 포커스를 둘 썸네일 순번
    focusImageIndex?: number
}

function ProductDetailModal({ product, onClose, onRemove, onImageClick, focusImageIndex }: ProductDetailModalProps) {
    const { type, title, link, content, images, productImageFile } = product;
    const isUrl = type === SourceType.Url;

    const mainImageFiles = useMemo(() => (productImageFile ? [productImageFile] : NO_FILES), [productImageFile]);
    const [thumbnail] = useObjectUrls(mainImageFiles);

    return (
        <Modal
            title={title}
            onClose={onClose}
            footer={
                <>
                    <Button text="목록에서 삭제" onClick={onRemove} variant="secondary" fontSize={15} className="flex-1 md:flex-none" />
                    <Button text="닫기" onClick={onClose} fontSize={15} className="flex-1 md:flex-none" />
                </>
            }
        >
            <div className="flex flex-col gap-5">
                <div className="flex items-center gap-3">
                    <img src={thumbnail ? thumbnail : defaultThumbnail}
                        alt="상품 썸네일"
                        className="size-14 shrink-0 rounded-xl border border-box-line object-cover" />
                    <div className="flex items-center gap-1">
                        <img src={isUrl ? urlIcon : imageIcon} alt="" className="size-4" />
                        <p className="text-sm font-bold text-neutral-border">{isUrl ? "URL" : "이미지 / 텍스트"}</p>
                    </div>
                </div>
                {isUrl ? (
                    <div className="flex flex-col gap-1">
                        <h3 className="text-base font-bold text-black">링크</h3>
                        {link && isHttpUrl(link) ? (
                            <p className="text-sm break-all">
                                <a href={link} target="_blank" rel="noopener noreferrer" className="text-primary underline">
                                    {link}
                                </a>
                            </p>
                        ) : (
                            <p className="text-sm text-neutral-text break-all">{link}</p>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col gap-5">
                        {content && (
                            <div className="flex flex-col gap-1">
                                <h3 className="text-base font-bold text-black">내용</h3>
                                <p className="whitespace-pre-line text-sm text-neutral-text">{content}</p>
                            </div>
                        )}
                        {images && images.length > 0 && (
                            <AttachedImageList
                                title="상세페이지 이미지"
                                files={images}
                                thumbnailSize="sm"
                                onImageClick={onImageClick}
                                focusIndex={focusImageIndex}
                            />
                        )}
                    </div>
                )}
            </div>
        </Modal>
    );
}

export default ProductDetailModal;
