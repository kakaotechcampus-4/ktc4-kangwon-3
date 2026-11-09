import { useEffect, useState } from "react";

import { SourceType } from "@/api/types/common.ts"
import deleteIcon from "@/assets/delete-gray.svg"
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import imageIcon from "@/assets/upload-img_txt.svg"
import toggleIcon from "@/assets/upload-toggle.svg"
import urlIcon from "@/assets/upload-url.svg"
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/cn";
import { truncateWithEllipsis } from "@/lib/text";
import { isHttpUrl } from "@/lib/url";

import AttachedImageList from "./AttachedImageList.tsx"

interface AddedProductProps {
    type: SourceType;
    title: string;
    productImageFile?: File;
    link?: string;
    content?: string;
    images?: File[];
    onRemove: () => void;
}

const MAX_DISPLAY_TITLE_LENGTH = 40;

function AddedProduct({ type, title, productImageFile, link, content, images, onRemove }: AddedProductProps) {
    const [expanded, setExpanded] = useState(false);
    const [thumbnail, setThumbnail] = useState<string | undefined>(undefined);
    const isMobile = useIsMobile();
    // 모바일은 원본 제목을 넘기고 CSS(truncate)가 한 줄에서 자른다. 데스크톱은 글자 수로 줄인다.
    const displayTitle = isMobile ? title : truncateWithEllipsis(title, MAX_DISPLAY_TITLE_LENGTH);
    // 제목이 잘렸을 수 있으면(모바일은 항상) 마우스를 올렸을 때 전체 제목을 보여준다.
    const isTitleLong = isMobile || displayTitle !== title;

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
        <DefaultBox>
            <div className="relative flex w-full gap-4 pb-9 md:gap-5 md:pb-4">
                <img src={thumbnail ? thumbnail : defaultThumbnail}
                    alt="상품 썸네일"
                    className="size-16 object-cover rounded-lg border border-box-line md:size-20" />
                <div className="flex min-w-0 flex-col gap-3 pr-7 md:pr-0">
                    <div className="flex gap-2 items-center">
                        <img src={type === SourceType.Url ? urlIcon : imageIcon}
                            alt=""
                            className="w-5 h-5" />
                        <p className="text-base text-neutral-border font-bold">{type === SourceType.Url ? "URL" : "이미지 / 텍스트"}</p>
                    </div>
                    <h3 title={isTitleLong ? title : undefined} className="truncate text-base font-bold text-neutral-dark md:overflow-visible md:text-clip md:whitespace-normal md:text-xl">{displayTitle}</h3>
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
                    aria-expanded={expanded}
                    className="absolute bottom-0 right-0 flex cursor-pointer items-center gap-1"
                >
                    <p className="text-base font-semibold text-neutral-border">{expanded ? "접기" : "자세히 보기"}</p>
                    <img
                        src={toggleIcon}
                        alt=""
                        className={cn("h-5 w-5 transition-transform", expanded && "rotate-180")}
                    />
                </button>
            </div>
            {expanded && (
                <div className="flex w-full flex-col gap-3 border-t border-neutral-line pt-3">
                    {type === SourceType.Url ? (
                        <div className="flex flex-col gap-1">
                            <p className="text-lg font-bold text-black">링크</p>
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