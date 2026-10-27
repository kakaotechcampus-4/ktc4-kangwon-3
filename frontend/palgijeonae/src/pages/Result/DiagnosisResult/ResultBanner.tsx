import { Link } from "react-router-dom";

import type { ProductFailure } from "@/api/product";
import { ProcessingStatusType, ResultStatus } from "@/api/types";
import dangerIcon from "@/assets/result-danger.svg";
import noResultIcon from "@/assets/result-noResult.svg";
import successIcon from "@/assets/result-success.svg";
import warningIcon from "@/assets/result-warning.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

// 배너 하단 액션 버튼의 종류. 상태 조합당 최대 하나만 쓰인다.
enum BannerAction {
    NextSteps = "nextSteps",
    Retry = "retry",
    Judgement = "judgement",
    Question = "question",
}

// resultStatus, processingStatus, failure의 조합으로 결정되는 배너 상태
enum BannerCaseKey {
    Success = "SUCCESS",
    Danger = "DANGER",
    Warning = "WARNING",
    Pending = "PENDING",
    InProgress = "IN_PROGRESS",
    AwaitingInput = "AWAITING_INPUT",
    CompletedNoResult = "COMPLETED_NO_RESULT",
    FailedUnknown = "FAILED_UNKNOWN",
    FailedRetryable = "FAILED_RETRYABLE",
    FailedNotRetryable = "FAILED_NOT_RETRYABLE",
}

/** 상태값으로 배너 케이스를 결정한다 */
function resolveBannerCase(
    resultStatus: ResultStatus | null,
    processingStatus: ProcessingStatusType,
    failure: ProductFailure | null,
): BannerCaseKey {
    switch (resultStatus) {
        case ResultStatus.PurchasingAgentAllowed: return BannerCaseKey.Success;
        case ResultStatus.DirectImportCertificationRequired: return BannerCaseKey.Danger;
        case ResultStatus.RecheckRequired: return BannerCaseKey.Warning;
    }

    switch (processingStatus) {
        case ProcessingStatusType.Pending: return BannerCaseKey.Pending;
        case ProcessingStatusType.InProgress: return BannerCaseKey.InProgress;
        case ProcessingStatusType.AwaitingInput: return BannerCaseKey.AwaitingInput;
        case ProcessingStatusType.Completed: return BannerCaseKey.CompletedNoResult;
        case ProcessingStatusType.Failed:
            // retryable이 거짓이면 다시 시도해도 같은 결과라 재시도를 권하지 않는다.
            if (!failure) return BannerCaseKey.FailedUnknown;
            return failure.retryable ? BannerCaseKey.FailedRetryable : BannerCaseKey.FailedNotRetryable;
    }
}

interface BannerConfig {
    tone: "success" | "warning" | "danger" | "neutral"
    icon: string
    textColorClass: string
    buttonColorClass: string
    // summary가 없을 때 보여줄 기본 설명. failure 메시지가 필요한 경우만 함수로.
    description?: string | ((failure: ProductFailure | null) => string)
    action?: BannerAction
}

// 결과/진행 상태가 없을 때 공통으로 쓰는 중립 스타일.
const NEUTRAL_VISUAL = {
    tone: "neutral" as const,
    icon: noResultIcon,
    textColorClass: "text-neutral-border",
    buttonColorClass: "bg-neutral-border",
};

// 케이스별로 보여줄 스타일·설명·액션을 한 곳에서 정의한다.
const BANNER_CONFIG: Record<BannerCaseKey, BannerConfig> = {
    [BannerCaseKey.Success]: {
        tone: "success",
        icon: successIcon,
        textColorClass: "text-status-success",
        buttonColorClass: "bg-status-success",
    },
    [BannerCaseKey.Danger]: {
        tone: "danger",
        icon: dangerIcon,
        textColorClass: "text-status-danger",
        buttonColorClass: "bg-status-danger",
        action: BannerAction.NextSteps,
    },
    [BannerCaseKey.Warning]: {
        tone: "warning",
        icon: warningIcon,
        textColorClass: "text-status-warning",
        buttonColorClass: "bg-status-warning",
        action: BannerAction.NextSteps,
    },
    [BannerCaseKey.Pending]: {
        ...NEUTRAL_VISUAL,
        description: "진단 대기 중이에요. 잠시만 기다려 주세요.",
    },
    [BannerCaseKey.InProgress]: {
        ...NEUTRAL_VISUAL,
        description: "진단이 진행 중이에요.",
        action: BannerAction.Judgement,
    },
    [BannerCaseKey.AwaitingInput]: {
        ...NEUTRAL_VISUAL,
        description: "답변이 필요한 질문이 있어요.",
        action: BannerAction.Question,
    },
    [BannerCaseKey.CompletedNoResult]: {
        ...NEUTRAL_VISUAL,
    },
    [BannerCaseKey.FailedUnknown]: {
        ...NEUTRAL_VISUAL,
        description: "진단에 실패했어요.",
    },
    [BannerCaseKey.FailedRetryable]: {
        ...NEUTRAL_VISUAL,
        description: (failure) => `진단에 실패했어요. 다시 시도해 주세요.\n${failure?.errorMessage ?? ""}`,
        action: BannerAction.Retry,
    },
    [BannerCaseKey.FailedNotRetryable]: {
        ...NEUTRAL_VISUAL,
        description: (failure) => `진단을 완료할 수 없어요.\n${failure?.errorMessage ?? ""}`,
    },
};

const BANNER_ACTION_LABELS: Record<BannerAction, string> = {
    [BannerAction.NextSteps]: "다음 단계 보기 →",
    [BannerAction.Retry]: "다시 시도 →",
    [BannerAction.Judgement]: "진행 상황 확인 →",
    [BannerAction.Question]: "질문에 답변하기 →",
};

const ACTION_BUTTON_CLASS = "cursor-pointer rounded-full px-5 py-3 text-sm font-semibold text-white";

interface ResultBannerProps {
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    summary: string | null
    requiredActions: string[]
    failure: ProductFailure | null
    diagnosesId?: string
    onNextStepsClick: () => void
}

function ResultBanner({ resultStatus, processingStatus, summary, requiredActions, failure, diagnosesId, onNextStepsClick }: ResultBannerProps) {
    const config = BANNER_CONFIG[resolveBannerCase(resultStatus, processingStatus, failure)];

    const statusLabel = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus].label
        : PROCESSING_STATUS_BADGES[processingStatus]?.label ?? FALLBACK_BADGE.label;

    // 해야 할 일 건수는 사입 인증 필요/재확인 필요 결과일 때만 보여준다.
    const showRequiredActionsCount = resultStatus != null && resultStatus !== ResultStatus.PurchasingAgentAllowed;
    const title = showRequiredActionsCount ? `${statusLabel} · 해야 할 일 ${requiredActions.length}건` : statusLabel;
    const description = summary
        ?? (typeof config.description === "function" ? config.description(failure) : config.description)
        ?? "";

    // Judgement/Question은 화면 이동이 필요한 액션이라 diagnosesId가 있어야 보여준다.
    const needsDiagnosesId = config.action === BannerAction.Judgement || config.action === BannerAction.Question;
    const action = config.action && (!needsDiagnosesId || diagnosesId) ? config.action : undefined;
    const actionPath = action === BannerAction.Judgement ? `/judgement/${diagnosesId}`
        : action === BannerAction.Question ? `/question/${diagnosesId}`
        : undefined;

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
