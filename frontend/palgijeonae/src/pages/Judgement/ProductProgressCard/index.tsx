import { Link } from "react-router-dom";

import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";
import { countGraphemes, truncateGraphemes } from "@/lib/text";

import ProgressBar from "./ProgressBar";
import ProgressSweep from "./ProgressSweep";
import StatusBadge from "./StatusBadge";
import { getStatusDescription } from "./statusDescription";
import { getStatusNotice } from "./statusNotice";
import { isRunningStatus, useStatusTransition } from "./useStatusTransition";

const CARD_BORDER_TONE: Record<ProcessingStatusType, "neutral" | "success" | "warning" | "danger"> = {
    [ProcessingStatusType.Pending]: "neutral",
    [ProcessingStatusType.InProgress]: "neutral",
    [ProcessingStatusType.AwaitingInput]: "warning",
    [ProcessingStatusType.Completed]: "success",
    [ProcessingStatusType.Failed]: "danger",
};

const ACTION_BUTTON_BASE_CLASS = "shrink-0 cursor-pointer rounded-full border bg-white px-5 py-2.5 text-sm font-semibold";

// 상태가 바뀐 순간 카드 위에 잠깐 깔리는 하이라이트 색.
const FLASH_BG: Record<ProcessingStatusType, string> = {
    [ProcessingStatusType.Pending]: "bg-primary/10",
    [ProcessingStatusType.InProgress]: "bg-primary/10",
    [ProcessingStatusType.AwaitingInput]: "bg-status-warning-bg",
    [ProcessingStatusType.Completed]: "bg-status-success-bg",
    [ProcessingStatusType.Failed]: "bg-status-danger-bg",
};

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
    const { productId, productName, productImageUrl, progresses } = product;
    const { displayStatus, finishing, animationKey, contentKey } = useStatusTransition(product.processingStatus);
    // 상태 전환 중에는 실제 processingStatus 대신 표시용 상태(displayStatus)로 배지/설명/버튼/테두리를 계산한다.
    const displayProduct = { ...product, processingStatus: displayStatus };
    const description = getStatusDescription(displayProduct);
    const action = ACTION_CONFIG[displayStatus];
    const notice = getStatusNotice(displayProduct);
    const showProgressBar = isRunningStatus(displayStatus);
    const showProgressSweep = showProgressBar && !finishing;

    return (
        <DefaultBox
            borderTone={CARD_BORDER_TONE[displayStatus]}
            className="relative overflow-hidden transition-colors duration-300"
        >
            {animationKey != null && (
                <span
                    key={`flash-${animationKey}`}
                    aria-hidden="true"
                    className={cn("pointer-events-none absolute inset-0 opacity-0 motion-safe:animate-status-flash", FLASH_BG[displayStatus])}
                />
            )}
            {showProgressSweep && <ProgressSweep />}
            <div className="relative flex w-full flex-col gap-5">
                <div className="flex w-full flex-row items-center justify-between gap-4">
                    <div className="flex flex-row items-center gap-4">
                        {/* 상태와 무관한 요소라 remount 대상에서 제외 — 안 그러면 전환마다 썸네일이 다시 그려진다 */}
                        <img
                            src={productImageUrl ?? defaultThumbnail}
                            alt="상품 썸네일"
                            className="h-16 w-16 shrink-0 rounded-lg border border-neutral-border object-cover"
                        />
                        <div className="flex flex-col items-start gap-1">
                            <div
                                key={`badge-${contentKey}`}
                                className={cn("flex items-center gap-2", animationKey != null && "motion-safe:animate-status-fade")}
                            >
                                <h2 className="text-lg font-bold text-black">{truncateProductName(productName)}</h2>
                                <StatusBadge processingStatus={displayStatus} />
                            </div>
                            <p
                                key={`desc-${contentKey}`}
                                className={cn("text-sm text-neutral-muted", animationKey != null && "motion-safe:animate-status-fade")}
                            >
                                {description}
                            </p>
                        </div>
                    </div>
                    {/* 포커스를 유지해야 하니 remount 대상에서 제외 — 상태가 바뀌어도 링크를 새로 만들지 않고 href/라벨만 갱신 */}
                    {action && (
                        <Link to={action.buildPath(productId)} className={cn(ACTION_BUTTON_BASE_CLASS, action.className)}>
                            {action.label}
                        </Link>
                    )}
                </div>
                {(showProgressBar || notice) && (
                    <div
                        key={`body-${contentKey}`}
                        className={cn("flex w-full flex-col gap-5", animationKey != null && "motion-safe:animate-status-fade")}
                    >
                        {showProgressBar && <ProgressBar progresses={progresses} finishing={finishing} />}
                        {notice && (
                            <div className={cn("flex w-full rounded-xl px-4 py-3", notice.className)}>
                                <p className="flex-1 text-sm leading-normal">{notice.text}</p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </DefaultBox>
    );
}

export default ProductProgressCard;
