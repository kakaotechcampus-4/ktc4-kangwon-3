import { type ProcessingStatusType, type ResultStatus, type SourceType } from "@/api/types/common";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES, SOURCE_TYPE_INFO } from "@/constants/statusBadges";
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
}

function ProductPreview({ productName, productImageUrl, resultStatus, processingStatus, sourceType }: ProductPreviewProps) {
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;
    const displayTitle = truncateWithEllipsis(productName, MAX_DISPLAY_TITLE_LENGTH);
    const isProductNameLong = productName.length > MAX_DISPLAY_TITLE_LENGTH;

    return (
        <DefaultBox>
            <div className="flex w-full flex-row gap-4">
                <img src={productImageUrl ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-23 h-23 shrink-0 object-cover rounded-lg border border-neutral-border" />
                <div className="flex min-w-0 flex-col items-start gap-2">
                    <div className="flex items-center gap-2">
                        <div className={cn("px-2.5 py-1 border rounded-full text-sm font-semibold", badge.className)}>
                            {badge.label}
                        </div>
                        <img src={SOURCE_TYPE_INFO[sourceType].icon}
                            alt={SOURCE_TYPE_INFO[sourceType].label}
                            className="w-5 h-5" />
                        <p className="text-base text-neutral-border font-semibold">{SOURCE_TYPE_INFO[sourceType].label}</p>
                    </div>
                    <h3 title={isProductNameLong ? productName : undefined} className="text-xl font-bold text-black">{displayTitle}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default ProductPreview;
