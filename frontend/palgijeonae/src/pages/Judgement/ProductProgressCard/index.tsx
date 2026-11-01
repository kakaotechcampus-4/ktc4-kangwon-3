import { Link } from "react-router-dom";

import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";
import { countGraphemes, truncateGraphemes } from "@/lib/text";

import ProgressBar from "./ProgressBar";
import StatusBadge from "./StatusBadge";
import { getStatusDescription } from "./statusDescription";
import { getStatusNotice } from "./statusNotice";

const CARD_BORDER_TONE: Record<ProcessingStatusType, "neutral" | "success" | "warning" | "danger"> = {
    [ProcessingStatusType.Pending]: "neutral",
    [ProcessingStatusType.InProgress]: "neutral",
    [ProcessingStatusType.AwaitingInput]: "warning",
    [ProcessingStatusType.Completed]: "success",
    [ProcessingStatusType.Failed]: "danger",
};

const ACTION_BUTTON_BASE_CLASS = "shrink-0 cursor-pointer rounded-full border bg-white px-5 py-2.5 text-sm font-semibold";

// 상품명을 몇 글자까지 보여줄 지 결정
const MAX_PRODUCT_NAME_LENGTH = 30;

const truncateProductName = (name: string) =>
    countGraphemes(name) > MAX_PRODUCT_NAME_LENGTH ? `${truncateGraphemes(name, MAX_PRODUCT_NAME_LENGTH)}...` : name;

interface ActionConfig {
    label: string
    buildPath: (productId: string) => string
    // 상태별 테두리/글자 색. 피그마 상 흰 배경 + 상태 색 테두리·텍스트 조합.
    className: string
}

// 답변이 필요하거나 완료된 상품만 버튼이 있다.
const ACTION_CONFIG: Partial<Record<ProcessingStatusType, ActionConfig>> = {
    [ProcessingStatusType.AwaitingInput]: {
        label: "질문에 답변하기 →",
        buildPath: (productId) => `/question/${productId}`,
        className: "border-status-warning text-status-warning",
    },
    [ProcessingStatusType.Completed]: {
        label: "결과 보기",
        buildPath: (productId) => `/result/product/${productId}`,
        className: "border-black text-black",
    },
};

interface ProductProgressCardProps {
    product: ProductResult
}

function ProductProgressCard({ product }: ProductProgressCardProps) {
    const { productId, productName, productImageUrl, processingStatus, progresses } = product;
    const description = getStatusDescription(product);
    const action = ACTION_CONFIG[processingStatus];
    const notice = getStatusNotice(product);
    const showProgressBar = processingStatus === ProcessingStatusType.Pending || processingStatus === ProcessingStatusType.InProgress;

    return (
        <DefaultBox borderTone={CARD_BORDER_TONE[processingStatus]}>
            <div className="flex w-full flex-row items-center justify-between gap-4">
                <div className="flex flex-row items-center gap-4">
                    <img
                        src={productImageUrl ?? defaultThumbnail}
                        alt="상품 썸네일"
                        className="h-16 w-16 shrink-0 rounded-lg border border-neutral-border object-cover"
                    />
                    <div className="flex flex-col items-start gap-1">
                        <div className="flex items-center gap-2">
                            <h2 className="text-lg font-bold text-black">{truncateProductName(productName)}</h2>
                            <StatusBadge processingStatus={processingStatus} />
                        </div>
                        <p className="text-sm text-neutral-muted">{description}</p>
                    </div>
                </div>
                {action && (
                    <Link to={action.buildPath(productId)} className={cn(ACTION_BUTTON_BASE_CLASS, action.className)}>
                        {action.label}
                    </Link>
                )}
            </div>
            {showProgressBar && <ProgressBar progresses={progresses} />}
            {notice && (
                <div className={cn("flex w-full rounded-xl px-4 py-3", notice.className)}>
                    <p className="flex-1 text-sm leading-normal">{notice.text}</p>
                </div>
            )}
        </DefaultBox>
    );
}

export default ProductProgressCard;
