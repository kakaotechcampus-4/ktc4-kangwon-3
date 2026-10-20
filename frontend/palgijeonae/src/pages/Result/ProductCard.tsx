import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES, SOURCE_TYPE_INFO } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

interface MyProductProps {
    productName: string
    productImageUrl?: string | null
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    sourceType: SourceType
}

function MyProduct({productName, productImageUrl, resultStatus, processingStatus, sourceType}: MyProductProps) {
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;

    return (
        <DefaultBox>
            <div
                className={cn("flex flex-row w-full gap-4")}
            >
                <img src={productImageUrl ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-23 h-23 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col items-start gap-2">
                    <div className={cn("px-2.5 py-1 border rounded-full text-sm font-semibold", badge.className)}>
                        {badge.label}
                    </div>
                    <div className="flex gap-2 items-center">
                        <img src={SOURCE_TYPE_INFO[sourceType].icon}
                            alt={SOURCE_TYPE_INFO[sourceType].label}
                            className="w-5 h-5" />
                        <p className="text-base text-neutral-border font-semibold">{SOURCE_TYPE_INFO[sourceType].label}</p>
                    </div>
                    <h3 className="text-lg font-semibold pl-1">{productName}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default MyProduct;
