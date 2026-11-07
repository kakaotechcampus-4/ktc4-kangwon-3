import type { ProductFailure } from "@/api/product";
import { ProcessingStatusType, ResultStatus } from "@/api/types";
import dangerIcon from "@/assets/result-danger.svg";
import noResultIcon from "@/assets/result-noResult.svg";
import successIcon from "@/assets/result-success.svg";
import warningIcon from "@/assets/result-warning.svg";

// 배너 하단 액션 버튼의 종류. 상태 조합당 최대 하나만 쓰인다.
export enum BannerAction {
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

export interface BannerConfig {
    tone: "success" | "warning" | "danger" | "neutral"
    icon: string
    textColorClass: string
    buttonColorClass: string
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

export const BANNER_ACTION_LABELS: Record<BannerAction, string> = {
    [BannerAction.NextSteps]: "다음 단계 보기 →",
    [BannerAction.Retry]: "다시 시도 →",
    [BannerAction.Judgement]: "진행 상황 확인 →",
    [BannerAction.Question]: "질문에 답변하기 →",
};

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

/** 상태값으로 배너에 보여줄 설정을 결정한다 */
export function resolveBannerConfig(
    resultStatus: ResultStatus | null,
    processingStatus: ProcessingStatusType,
    failure: ProductFailure | null,
): BannerConfig {
    return BANNER_CONFIG[resolveBannerCase(resultStatus, processingStatus, failure)];
}
