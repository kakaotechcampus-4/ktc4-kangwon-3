import { Link, useLocation } from "react-router-dom";

import { ProcessingStatusType } from "@/api/types/common";
import type { ProductResult } from "@/api/types/product";
import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/cn";
import { createFromState } from "@/lib/fromState";
import { truncateWithEllipsis } from "@/lib/text";

import { useAnimateOnChange } from "../hooks/useAnimateOnChange";
import { useStatusChangeCount } from "../hooks/useStatusChangeCount";
import { getStatusDescription } from "../utils/statusDescription";
import { getStatusNotice } from "../utils/statusNotice";
import ProgressBar from "./ProgressBar";
import ProgressSweep from "./ProgressSweep";
import StatusBadge from "./StatusBadge";
import StatusFlash from "./StatusFlash";

const CARD_BORDER_TONE: Record<ProcessingStatusType, "neutral" | "success" | "warning" | "danger"> = {
    [ProcessingStatusType.Pending]: "neutral",
    [ProcessingStatusType.InProgress]: "neutral",
    [ProcessingStatusType.AwaitingInput]: "warning",
    [ProcessingStatusType.Completed]: "success",
    [ProcessingStatusType.Failed]: "danger",
};

const ACTION_BUTTON_BASE_CLASS = "w-full shrink-0 cursor-pointer rounded-full border bg-white px-5 py-2.5 text-center text-sm font-semibold md:w-auto shadow-button-secondary transition-colors duration-150 outline-none focus-visible:ring-3";

// 컴포넌트 안에서 만들면 렌더마다 새 배열/객체가 생겨 useAnimateOnChange의 effect가 매번 재실행된다
const FADE_KEYFRAMES: Keyframe[] = [{ opacity: 0.25 }, { opacity: 1 }];
const FADE_OPTIONS: KeyframeAnimationOptions = { duration: 250, easing: "ease-out" };

// 상품명을 몇 글자까지 보여줄 지 결정
const MAX_PRODUCT_NAME_LENGTH = 30;

interface ActionConfig {
    label: string
    buildPath: (productId: string) => string
    className: string
}

// 답변이 필요하거나 완료, 실패한 상품만 버튼 노출. 실패한 상품은 결과 화면에서 재진단할 수 있다.
const ACTION_CONFIG: Partial<Record<ProcessingStatusType, ActionConfig>> = {
    [ProcessingStatusType.AwaitingInput]: {
        label: "질문에 답변하기 →",
        buildPath: (productId) => `/question/${productId}`,
        className: "border-status-warning/40 text-status-warning hover:border-status-warning/60 hover:bg-status-warning-bg focus-visible:ring-status-warning/20",
    },
    [ProcessingStatusType.Completed]: {
        label: "결과 보기",
        buildPath: (productId) => `/result/product/${productId}`,
        className: "border-status-success/40 text-status-success hover:border-status-success/60 hover:bg-status-success-bg focus-visible:ring-status-success/20",
    },
    [ProcessingStatusType.Failed]: {
        label: "결과 보기",
        buildPath: (productId) => `/result/product/${productId}`,
        className: "border-status-danger/40 text-status-danger hover:border-status-danger/60 hover:bg-status-danger-bg focus-visible:ring-status-danger/20",
    },
};

interface ProductProgressCardProps {
    product: ProductResult
}

/**
 * Judgement 페이지의 진행 카드 하나. 상품 상태(진행 중/답변 필요/완료/실패)에 맞춰
 * 썸네일·배지·설명·진행 막대·안내 문구·액션 버튼을 보여주고, 상태 전환 애니메이션을 재생한다.
 */
function ProductProgressCard({ product }: ProductProgressCardProps) {
    const { productId, productName, productImageUrl, processingStatus, progresses } = product;


    // 화면 상태가 실제로 바뀔 때마다 증가하는 트리거 값(첫 렌더는 0 → 효과 없음).
    // 모바일은 원본 이름을 넘기고 CSS(truncate)가 한 줄에서 자른다. 데스크톱은 줄바꿈되므로 글자 수로 줄인다.
    const isMobile = useIsMobile();
    const location = useLocation();
    const displayName = isMobile ? productName : truncateWithEllipsis(productName, MAX_PRODUCT_NAME_LENGTH);
    const changeCount = useStatusChangeCount(processingStatus);
    // changeCount가 바뀐 순간에만 카드 내용 크로스페이드를 한 번 재생한다.
    const contentRef = useAnimateOnChange<HTMLDivElement>(changeCount, FADE_KEYFRAMES, FADE_OPTIONS);
    // PENDING도 IN_PROGRESS와 같은 "진행 중"으로 취급한다.
    const isRunning = processingStatus === ProcessingStatusType.Pending || processingStatus === ProcessingStatusType.InProgress;

    
    // 카드에 띄울 설명, 액션 버튼, 부가 설명
    const description = getStatusDescription(product);
    const action = ACTION_CONFIG[processingStatus];
    const notice = getStatusNotice(product);

    return (
        <DefaultBox
            borderTone={CARD_BORDER_TONE[processingStatus]}
            className="relative overflow-hidden transition-colors duration-300"
        >
            <StatusFlash status={processingStatus} trigger={changeCount} />
            {isRunning && <ProgressSweep />}
            <div ref={contentRef} className="relative flex w-full flex-col gap-5">
                <div className="flex w-full flex-col items-stretch gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="flex min-w-0 flex-row items-center gap-4">
                        <img
                            src={productImageUrl ?? defaultThumbnail}
                            alt=""
                            className="size-14 shrink-0 rounded-lg border border-box-line object-cover md:size-16"
                        />
                        <div className="flex min-w-0 flex-col items-start gap-2">
                            <div className="flex max-w-full items-center gap-2 md:flex-wrap">
                                <h2 title={isMobile || displayName !== productName ? productName : undefined} className="min-w-0 truncate text-base font-bold text-black md:overflow-visible md:text-clip md:whitespace-normal md:text-lg">{displayName}</h2>
                                <StatusBadge processingStatus={processingStatus} />
                            </div>
                            <p className="text-sm text-neutral-muted">{description}</p>
                        </div>
                    </div>
                    {action && (
                        <Link to={action.buildPath(productId)} state={createFromState(location)} className={cn(ACTION_BUTTON_BASE_CLASS, action.className)}>
                            {action.label}
                        </Link>
                    )}
                </div>
                {isRunning && <ProgressBar progresses={progresses} />}
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
