import { Link } from "react-router-dom";

import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";
import { countGraphemes, truncateGraphemes } from "@/lib/text";

import ProgressBar from "./components/ProgressBar";
import ProgressSweep from "./components/ProgressSweep";
import StatusBadge from "./components/StatusBadge";
import StatusFlash from "./components/StatusFlash";
import { useAnimateOnChange } from "./hooks/useAnimateOnChange";
import { isRunningStatus, useStatusTransition } from "./hooks/useStatusTransition";
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

// 의존성 배열에 들어가므로 반드시 모듈 상수로 둔다
const FADE_KEYFRAMES: Keyframe[] = [{ opacity: 0.25 }, { opacity: 1 }];
const FADE_OPTIONS: KeyframeAnimationOptions = { duration: 250, easing: "ease-out" };

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
    const { displayStatus, isFinishing, changeCount } = useStatusTransition(product.processingStatus);
    const contentRef = useAnimateOnChange<HTMLDivElement>(changeCount, FADE_KEYFRAMES, FADE_OPTIONS);
    const isRunning = isRunningStatus(displayStatus);
    // 상태 전환 중에는 실제 processingStatus 대신 표시용 상태(displayStatus)로 배지/설명/버튼/테두리를 계산한다.
    const displayProduct = { ...product, processingStatus: displayStatus };
    const description = getStatusDescription(displayProduct);
    const action = ACTION_CONFIG[displayStatus];
    const notice = getStatusNotice(displayProduct);

    return (
        <DefaultBox
            borderTone={CARD_BORDER_TONE[displayStatus]}
            className="relative overflow-hidden transition-colors duration-300"
        >
            <StatusFlash status={displayStatus} trigger={changeCount} />
            {isRunning && !isFinishing && <ProgressSweep />}
            <div ref={contentRef} className="relative flex w-full flex-col gap-5">
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
                                <StatusBadge processingStatus={displayStatus} />
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
                {isRunning && <ProgressBar progresses={progresses} finishing={isFinishing} />}
                {notice && (
                    <div className={cn("flex w-full rounded-xl px-4 py-3", notice.className)}>
                        <p className="flex-1 text-sm leading-normal">{notice.text}</p>
                    </div>
                )}
            </div>
        </DefaultBox>
    );
}

export default ProductProgressCard;
