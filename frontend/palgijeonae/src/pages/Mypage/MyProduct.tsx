import { useNavigate } from "react-router-dom";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";

import type { MyProductItem, ProcessingStatusType, ResultStatus } from "./types.ts";

type MyProductProps = MyProductItem;

interface Badge {
    label: string
    className: string
}

// 진단이 끝난 상품의 배지.
const RESULT_STATUS_BADGES: Record<ResultStatus, Badge> = {
    PURCHASING_AGENT_ALLOWED: { label: "구매 대행 가능", className: "text-status-success bg-status-success-bg" },
    DIRECT_IMPORT_CERTIFICATION_REQUIRED: { label: "사입 인증 필요", className: "text-status-danger bg-status-danger-bg" },
    RECHECK_REQUIRED: { label: "재확인 필요", className: "text-status-warning bg-status-warning-bg" },
};

// 진단이 끝나지 않은 상품의 배지.
const PROCESSING_STATUS_BADGES: Partial<Record<ProcessingStatusType, Badge>> = {
    PENDING: { label: "대기 중", className: "text-neutral-border bg-white" },
    IN_PROGRESS: { label: "진단 중", className: "text-neutral-border bg-white" },
    AWAITING_INPUT: { label: "입력 대기 중", className: "text-neutral-border bg-white" },
    FAILED: { label: "진단 실패", className: "text-status-danger bg-status-danger-bg" },
};

// 진단이 끝났지만 결과 상태가 없는 상품(오류)일 경우의 배지
const FALLBACK_BADGE: Badge = { label: "확인 중", className: "text-neutral-border bg-white" };

function MyProduct({ productName, processingStatus, resultStatus, productImageUrl }: MyProductProps) {
    const navigate = useNavigate();
    const badge = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus]
        : PROCESSING_STATUS_BADGES[processingStatus] ?? FALLBACK_BADGE;

    return (
        <DefaultBox>
            {/* TODO: Result 페이지 구현 시 /result/product?productId=로 변경. */}
            <div
                className="flex flex-row w-full gap-4 cursor-pointer"
                onClick={() => navigate("/result")}
            >
                <img src={productImageUrl ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-20 h-20 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col items-start gap-2">
                    <div className={cn("px-2.5 py-1 border rounded-full text-sm font-semibold", badge.className)}>
                        {badge.label}
                    </div>
                    <h3 className="text-lg font-semibold pl-1">{productName}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default MyProduct;
