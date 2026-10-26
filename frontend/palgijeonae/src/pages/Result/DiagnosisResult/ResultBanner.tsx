import { Link } from "react-router-dom";

import { ProcessingStatusType, ResultStatus } from "@/api/types";
import dangerIcon from "@/assets/result-danger.svg";
import noResultIcon from "@/assets/result-noResult.svg";
import successIcon from "@/assets/result-success.svg";
import warningIcon from "@/assets/result-warning.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

interface BannerStyle {
    tone: "success" | "warning" | "danger" | "neutral"
    icon: string
    textColorClass: string
    buttonColorClass: string
    showNextStepsButton: boolean
}

// 결과 상태별 배너 톤/아이콘/다음 단계 버튼 노출 여부
const BANNER_STYLE: Record<ResultStatus, BannerStyle> = {
    [ResultStatus.PurchasingAgentAllowed]: {
        tone: "success",
        icon: successIcon,
        textColorClass: "text-status-success",
        buttonColorClass: "bg-status-success",
        showNextStepsButton: false,
    },
    [ResultStatus.DirectImportCertificationRequired]: {
        tone: "danger",
        icon: dangerIcon,
        textColorClass: "text-status-danger",
        buttonColorClass: "bg-status-danger",
        showNextStepsButton: true,
    },
    [ResultStatus.RecheckRequired]: {
        tone: "warning",
        icon: warningIcon,
        textColorClass: "text-status-warning",
        buttonColorClass: "bg-status-warning",
        showNextStepsButton: true,
    },
};

// 결과 상태 값이 없는 스타일
const DEFAULT_BANNER_STYLE: BannerStyle = {
    tone: "neutral",
    icon: noResultIcon,
    textColorClass: "text-neutral-border",
    buttonColorClass: "bg-neutral-border",
    showNextStepsButton: false,
};

// 결과가 아직 없을 때 진행 상태별로 보여줄 안내 문구
const PROCESSING_STATUS_DESCRIPTIONS: Partial<Record<ProcessingStatusType, string>> = {
    [ProcessingStatusType.Pending]: "진단 대기 중이에요. 잠시만 기다려 주세요.",
    [ProcessingStatusType.InProgress]: "진단이 진행 중이에요. 눌러서 진행 상황을 확인하세요.",
    [ProcessingStatusType.AwaitingInput]: "답변이 필요한 질문이 있어요. 눌러서 질문에 답변해 주세요.",
    [ProcessingStatusType.Failed]: "진단에 실패했어요. 다시 시도해 주세요.",
};

interface ResultBannerProps {
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    summary: string | null
    requiredActions: string[]
    diagnosesId?: string
    onNextStepsClick: () => void
}

function ResultBanner({ resultStatus, processingStatus, summary, requiredActions, diagnosesId, onNextStepsClick }: ResultBannerProps) {
    const style = resultStatus ? BANNER_STYLE[resultStatus] : DEFAULT_BANNER_STYLE;

    // 결과가 아직 없으면 진행 상태(대기/진행중/입력대기/실패)별로 다른 문구를 보여준다.
    const statusLabel = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus].label
        : PROCESSING_STATUS_BADGES[processingStatus]?.label ?? FALLBACK_BADGE.label;
    // 성공했거나, 진단 결과가 없을 때는 해야할 일 건수를 숨김
    const hideRequiredActionsCount = resultStatus === ResultStatus.PurchasingAgentAllowed || !resultStatus;
    const title = hideRequiredActionsCount ? statusLabel : `${statusLabel} · 해야 할 일 ${requiredActions.length}건`;
    const description = summary ?? PROCESSING_STATUS_DESCRIPTIONS[processingStatus] ?? "";

    // 진행 중이면 판정 화면으로, 입력 대기 중이면 질문 화면으로 눌러서 이동할 수 있게 한다.
    const navigateTo = diagnosesId && processingStatus === ProcessingStatusType.InProgress
        ? `/judgement/${diagnosesId}`
        : diagnosesId && processingStatus === ProcessingStatusType.AwaitingInput
            ? `/question/${diagnosesId}`
            : undefined;

    const content = (
        <>
            <div className={cn("flex flex-row items-center gap-4", style.textColorClass)}>
                <img src={style.icon} alt="" className="h-10 w-10 shrink-0" />
                <div className="flex flex-col gap-2">
                    <p className="text-lg font-bold">{title || "진단 결과가 없어요"}</p>
                    <p className="whitespace-pre-line text-base font-medium">{description}</p>
                </div>
            </div>
            {style.showNextStepsButton && (
                <div className="flex w-full justify-end">
                    <button
                        type="button"
                        onClick={onNextStepsClick}
                        className={cn("cursor-pointer rounded-full px-5 py-3 text-sm font-semibold text-white", style.buttonColorClass)}
                    >
                        다음 단계 보기 →
                    </button>
                </div>
            )}
        </>
    );

    return (
        <DefaultBox tone={style.tone}>
            {navigateTo ? (
                <Link to={navigateTo} className="flex w-full cursor-pointer flex-col gap-5">
                    {content}
                </Link>
            ) : content}
        </DefaultBox>
    );
}

export default ResultBanner;
