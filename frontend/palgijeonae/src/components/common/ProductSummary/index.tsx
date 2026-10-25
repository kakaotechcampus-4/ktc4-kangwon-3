import { type ProcessingStatusType, type ResultStatus, type SourceType } from "@/api/types";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES, SOURCE_TYPE_INFO } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

interface ProductSummaryProps {
    productName: string
    productImageUrl?: string | null
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    sourceType: SourceType
}

function ProductSummary({ productName, productImageUrl, resultStatus, processingStatus, sourceType }: ProductSummaryProps) {
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;

    return (
        <div className="flex w-full flex-row gap-4">
            <img src={productImageUrl ?? defaultThumbnail}
                alt="상품 썸네일"
                className="w-23 h-23 object-cover rounded-lg border border-neutral-border" />
            <div className="flex flex-col items-start gap-2">
                <div className="flex items-center gap-2">
                    <div className={cn("px-2.5 py-1 border rounded-full text-sm font-semibold", badge.className)}>
                        {badge.label}
                    </div>
                    <img src={SOURCE_TYPE_INFO[sourceType].icon}
                        alt={SOURCE_TYPE_INFO[sourceType].label}
                        className="w-5 h-5" />
                    <p className="text-base text-neutral-border font-semibold">{SOURCE_TYPE_INFO[sourceType].label}</p>
                </div>
                <h3 className="text-xl font-bold text-black">{productName}</h3>
            </div>
        </div>
    );
}

export default ProductSummary;
