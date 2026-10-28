import { Link } from "react-router-dom";

import type { ProductResult } from "@/api/product";
import { ResultStatus } from "@/api/types";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

import { BANNER_ACTION_LABELS, BannerAction, resolveBannerConfig } from "./bannerConfig";

const ACTION_BUTTON_CLASS = "cursor-pointer rounded-full px-5 py-3 text-sm font-semibold text-white";

interface ResultBannerProps {
    product: ProductResult
    judgementPath?: string
    questionPath?: string
    onNextStepsClick: () => void
}

function ResultBanner({ product, judgementPath, questionPath, onNextStepsClick }: ResultBannerProps) {
    const { resultStatus, processingStatus, summary, requiredActions, failure } = product;
    const config = resolveBannerConfig(resultStatus, processingStatus, failure);

    const statusLabel = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus].label
        : PROCESSING_STATUS_BADGES[processingStatus]?.label ?? FALLBACK_BADGE.label;

    // 해야 할 일 건수는 사입 인증 필요/재확인 필요 결과일 때만 보여준다.
    const showRequiredActionsCount = resultStatus != null && resultStatus !== ResultStatus.PurchasingAgentAllowed;
    const title = showRequiredActionsCount ? `${statusLabel} · 해야 할 일 ${requiredActions.length}건` : statusLabel;
    const description = summary
        ?? (typeof config.description === "function" ? config.description(failure) : config.description)
        ?? "";

    const actionPath = config.action === BannerAction.Judgement ? judgementPath
        : config.action === BannerAction.Question ? questionPath
        : undefined;

    // 옳지 못한 상태(진단 중, 입력 대기 중)에서 결과 페이지에 접근한 경우 화면 이동(Judgement/Question)이 필요.
    const needsPath = config.action === BannerAction.Judgement || config.action === BannerAction.Question;
    // 경로가 필요한 액션인데 경로가 없으면(productId로 접근해 diagnosesId가 없는 경우 등) 버튼 자체를 숨긴다.
    const action = config.action && (!needsPath || actionPath) ? config.action : undefined;

    // TODO: 재진단 API/플로우가 정해지면 실제 재시도 로직으로 교체
    const handleRetryClick = () => {
        alert("재시도 기능은 아직 준비 중이에요.");
    };

    return (
        <DefaultBox tone={config.tone}>
            <div className={cn("flex flex-row items-center gap-4", config.textColorClass)}>
                <img src={config.icon} alt="" className="h-10 w-10 shrink-0" />
                <div className="flex flex-col gap-2">
                    <p className="text-lg font-bold">{title}</p>
                    <p className="whitespace-pre-line text-base font-medium">{description}</p>
                </div>
            </div>
            {action && (
                <div className="flex w-full justify-end">
                    {actionPath ? (
                        <Link
                            to={actionPath}
                            className={cn(ACTION_BUTTON_CLASS, config.buttonColorClass)}
                        >
                            {BANNER_ACTION_LABELS[action]}
                        </Link>
                    ) : (
                        <button
                            type="button"
                            onClick={action === BannerAction.Retry ? handleRetryClick : onNextStepsClick}
                            className={cn(ACTION_BUTTON_CLASS, config.buttonColorClass)}
                        >
                            {BANNER_ACTION_LABELS[action]}
                        </button>
                    )}
                </div>
            )}
        </DefaultBox>
    );
}

export default ResultBanner;
