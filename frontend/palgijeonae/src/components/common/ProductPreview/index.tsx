import { type ProcessingStatusType, type ResultStatus, type SourceType } from "@/api/types/common";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES, SOURCE_TYPE_INFO } from "@/constants/statusBadges";
import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/cn";
import { truncateWithEllipsis } from "@/lib/text";

// 제목이 길어도 레이아웃이 깨지지 않도록 화면에 보여줄 제목 길이를 제한한다.
const MAX_DISPLAY_TITLE_LENGTH = 40;

interface ProductPreviewProps {
    productName: string
    productImageUrl?: string | null
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    sourceType: SourceType
    // 카드 오른쪽 위에 삭제 버튼 같은 동작이 겹쳐 놓일 때, 좁은 화면에서 글자가 그 밑으로 들어가지 않도록 자리를 비워 둔다.
    hasTrailingAction?: boolean
    selected?: boolean
}

function ProductPreview({ productName, productImageUrl, resultStatus, processingStatus, sourceType, hasTrailingAction = false, selected = false }: ProductPreviewProps) {
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;
    const isMobile = useIsMobile();
    // 모바일은 원본 이름을 넘기고 CSS(line-clamp)가 두 줄에서 자른다. 데스크톱은 글자 수로 줄인다.
    const displayTitle = isMobile ? productName : truncateWithEllipsis(productName, MAX_DISPLAY_TITLE_LENGTH);
    const isProductNameLong = isMobile || displayTitle !== productName;

    return (
        <DefaultBox className={cn(selected && "border-primary/60 bg-primary-soft/30")}>
            <div className="flex w-full flex-row gap-3 md:gap-4">
                <img src={productImageUrl ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="size-16 shrink-0 object-cover rounded-lg border border-box-line md:size-23" />
                <div className={cn("flex min-w-0 flex-col items-start gap-1.5 md:gap-2", hasTrailingAction && "pr-14 md:pr-0")}>
                    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 md:gap-2">
                        <div className={cn("px-2 py-0.75 border rounded-full text-xs font-semibold md:px-2.5 md:py-1 md:text-sm", badge.className)}>
                            {badge.label}
                        </div>
                        <img src={SOURCE_TYPE_INFO[sourceType].icon}
                            alt={SOURCE_TYPE_INFO[sourceType].label}
                            className="size-4 md:size-5" />
                        <p className="text-[13px] text-neutral-border font-semibold md:text-base">{SOURCE_TYPE_INFO[sourceType].label}</p>
                    </div>
                    <h3 title={isProductNameLong ? productName : undefined} className="line-clamp-2 text-[15px] leading-5.5 font-bold text-black md:line-clamp-none md:text-xl md:leading-7">{displayTitle}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default ProductPreview;
