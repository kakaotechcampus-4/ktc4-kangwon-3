import { ResultStatus } from "@/api/types";
import dangerIcon from "@/assets/result-danger.svg";
import successIcon from "@/assets/result-success.svg";
import warningIcon from "@/assets/result-warning.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";

interface BannerStyle {
    tone: "success" | "warning" | "danger"
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

interface ResultBannerProps {
    resultStatus: ResultStatus
    title: string
    description: string
    onNextStepsClick: () => void
}

function ResultBanner({ resultStatus, title, description, onNextStepsClick }: ResultBannerProps) {
    const style = BANNER_STYLE[resultStatus];

    return (
        <DefaultBox tone={style.tone}>
            <div className={cn("flex flex-row items-center gap-4", style.textColorClass)}>
                <img src={style.icon} alt="" className="h-10 w-10 shrink-0" />
                <div className="flex flex-col gap-2">
                    <p className="text-lg font-bold">{title}</p>
                    <p className="whitespace-pre-line text-base font-medium">{description}</p>
                </div>
            </div>
            {style.showNextStepsButton && (
                <div className="flex w-full justify-end">
                    <button
                        type="button"
                        onClick={onNextStepsClick}
                        className={cn("cursor-pointer rounded-full px-5 py-2 text-sm font-semibold text-white", style.buttonColorClass)}
                    >
                        다음 단계 보기 →
                    </button>
                </div>
            )}
        </DefaultBox>
    );
}

export default ResultBanner;
