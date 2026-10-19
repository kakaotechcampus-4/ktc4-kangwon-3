import { useNavigate } from "react-router-dom";

import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types.ts"
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import imageIcon from "@/assets/upload-img_txt.svg"
import urlIcon from "@/assets/upload-url.svg"
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";

import type { MyProductItem } from "./types.ts";

type MyProductProps = MyProductItem;

// 결과 상태 / 진단 상태에 따른 배지
interface Badge {
    label: string
    className: string
}

// 입력 타입에 따른 아이콘
interface SourceTypeInfo {
    icon: string
    label: string
}

// 진단이 끝난 상품의 배지.
const RESULT_STATUS_BADGES: Record<ResultStatus, Badge> = {
    [ResultStatus.PurchasingAgentAllowed]: { label: "구매 대행 가능", className: "text-status-success bg-status-success-bg" },
    [ResultStatus.DirectImportCertificationRequired]: { label: "사입 인증 필요", className: "text-status-danger bg-status-danger-bg" },
    [ResultStatus.RecheckRequired]: { label: "재확인 필요", className: "text-status-warning bg-status-warning-bg" },
};

// 진단이 끝나지 않은 상품의 배지.
const PROCESSING_STATUS_BADGES: Partial<Record<ProcessingStatusType, Badge>> = {
    [ProcessingStatusType.Pending]: { label: "대기 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.InProgress]: { label: "진단 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.AwaitingInput]: { label: "입력 대기 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.Failed]: { label: "진단 실패", className: "text-status-danger bg-status-danger-bg" },
};

// 진단이 끝났지만 결과 상태가 없는 상품(오류)일 경우의 배지
const FALLBACK_BADGE: Badge = { label: "확인 중", className: "text-neutral-border bg-white" };

// 상품 등록 방식(URL/텍스트-이미지) 아이콘/라벨.
const SOURCE_TYPE_INFO: Record<SourceType, SourceTypeInfo> = {
    [SourceType.Url]: { icon: urlIcon, label: "URL" },
    [SourceType.TextImage]: { icon: imageIcon, label: "이미지 / 텍스트" },
};

function MyProduct({ productId, productName, productImageUrl, sourceType, processingStatus, resultStatus }: MyProductProps) {
    const navigate = useNavigate();
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;
    // 진단 결과가 없을 시 진단서 이동을 막기 위한 boolean 변수.
    const isDiagnosisComplete = resultStatus != null;

    const handleClick = () => {
        if (isDiagnosisComplete) {
            navigate(`/result/product/${productId}`);
        }
    };

    return (
        <DefaultBox>
            <div
                className={cn("flex flex-row w-full gap-4", isDiagnosisComplete && "cursor-pointer")}
                onClick={handleClick}
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
