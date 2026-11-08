import { Link } from "react-router-dom";

import { ResultStatus } from "@/api/types/common";
import type { ProductResult } from "@/api/types/product";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";
import { BANNER_ACTION_LABELS, BannerAction, resolveBannerConfig } from "@/pages/Result/components/DiagnosisResult/utils/bannerConfig";
import { useRetryDiagnosis } from "@/pages/Result/hooks/useRetryDiagnosis";

const ACTION_BUTTON_CLASS = "w-full cursor-pointer rounded-full px-5 py-3 text-center text-sm font-semibold text-white md:w-auto";

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

    // 진단 결과가 없는 상태(진단 중, 입력 대기 중)에서 결과 페이지에 접근한 경우 화면 이동(Judgement/Question)이 필요.
    const needsPath = config.action === BannerAction.Judgement || config.action === BannerAction.Question;
    // 경로가 필요한 액션인데 경로가 없으면(productId로 접근해 diagnosesId가 없는 경우 등) 버튼 자체를 숨긴다.
    const action = config.action && (!needsPath || actionPath) ? config.action : undefined;

    const { mutate: runRetryDiagnosis, isPending: isRetrying } = useRetryDiagnosis(product.productId, product.diagnosesId);

    return (
        <DefaultBox tone={config.tone}>
            <div className={cn("flex flex-row items-center gap-4", config.textColorClass)}>
                <img src={config.icon} alt="" className="size-8.5 shrink-0 md:size-10" />
                <div className="flex flex-col gap-2">
                    <p className="text-base font-bold md:text-lg">{title}</p>
                    <p className="whitespace-pre-line text-sm font-medium md:text-base">{description}</p>
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
                            onClick={action === BannerAction.Retry ? () => runRetryDiagnosis() : onNextStepsClick}
                            disabled={action === BannerAction.Retry && isRetrying}
                            className={cn(ACTION_BUTTON_CLASS, config.buttonColorClass, "disabled:cursor-default disabled:opacity-50")}
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
