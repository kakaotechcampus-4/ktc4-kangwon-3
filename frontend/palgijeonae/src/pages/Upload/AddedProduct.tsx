import { useState } from "react";

import deleteIcon from "@/assets/delete-gray.svg"
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import imageIcon from "@/assets/upload-img_txt.svg"
import toggleIcon from "@/assets/upload-toggle.svg"
import urlIcon from "@/assets/upload-url.svg"
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import { cn } from "@/lib/cn";

import AttachedImageList from "./form/AttachedImageList.tsx"
import type { DiagnosisStatus } from "./types.ts";

interface AddedProductProps {
    type: "url" | "text/image";
    title: string;
    thumbnail?: string;
    link?: string;
    content?: string;
    images?: File[];
    status?: DiagnosisStatus;
    onRemove: () => void;
}


function AddedProduct({ type, title, thumbnail, link, content, images, status, onRemove }: AddedProductProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <DefaultBox>
            <div className="relative flex w-full gap-5">
                <img src={thumbnail ? thumbnail : defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-20 h-20 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col gap-3">
                    <div className="flex gap-2 items-center">
                        <img src={type === "url" ? urlIcon : imageIcon}
                            alt={type === "url" ? "URL 아이콘" : "이미지 아이콘"}
                            className="w-5 h-5" />
                        <p className="text-base text-neutral-border font-bold">{type === "url" ? "URL" : "이미지 / 텍스트"}</p>
                    </div>
                    <h3 className="text-xl font-bold text-neutral-dark">{title}</h3>
                    {status?.state === "failed" && (
                        <p className="text-sm text-status-danger">진단 요청 실패 — 아래 재시도 버튼을 눌러주세요.</p>
                    )}
                    {status?.state === "pending" && (
                        <p className="text-sm text-neutral-border">진단 요청 중...</p>
                    )}
                </div>
                <button
                    type="button"
                    onClick={onRemove}
                    className="absolute top-0 right-0 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full bg-white"
                >
                    <img src={deleteIcon} alt="삭제" className="h-full w-full" />
                </button>
                <button
                    type="button"
                    onClick={() => setExpanded((prev) => !prev)}
                    className="absolute bottom-0 right-0 flex cursor-pointer items-center gap-1"
                >
                    <p className="text-base font-semibold text-neutral-border">{expanded ? "접기" : "자세히 보기"}</p>
                    <img
                        src={toggleIcon}
                        alt="토글 아이콘"
                        className={cn("h-5 w-5 transition-transform", expanded && "rotate-180")}
                    />
                </button>
            </div>
            {expanded && (
                <div className="flex w-full flex-col gap-3 border-t border-neutral-border pt-3">
                    {type === "url" ? (
                        <div className="flex flex-col gap-1">
                            <p className="text-lg font-bold text-black">링크</p>
                            <p className="text-sm text-neutral-text break-all">{link}</p>
                        </div>
                    ) : (
                        <>
                            {content && (
                                <div className="flex flex-col gap-1">
                                    <p className="text-lg font-bold text-black">내용</p>
                                    <p className="whitespace-pre-line text-sm text-neutral-text">{content}</p>
                                </div>
                            )}
                            {images && images.length > 0 && (
                                <AttachedImageList title="이미지" files={images} thumbnailSize="sm" />
                            )}
                        </>
                    )}
                </div>
            )}
        </DefaultBox>
     );
}

export default AddedProduct;