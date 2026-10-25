import { RiskLevel } from "@/api/product";
import { cn } from "@/lib/cn";

interface RiskMeterStyle {
    label: string
    filledCount: number
    barColorClass: string
    textColorClass: string
}

// 위험도별 채워지는 칸 수와 막대/텍스트 색. Unknown은 칸을 채우지 않고 점선으로 표시한다.
const RISK_METER_STYLE: Record<RiskLevel, RiskMeterStyle> = {
    [RiskLevel.High]: { label: "위험도 높음", filledCount: 3, barColorClass: "bg-status-danger", textColorClass: "text-status-danger" },
    [RiskLevel.Medium]: { label: "위험도 보통", filledCount: 2, barColorClass: "bg-status-warning", textColorClass: "text-status-warning" },
    [RiskLevel.Low]: { label: "위험도 낮음", filledCount: 1, barColorClass: "bg-status-success", textColorClass: "text-status-success" },
    [RiskLevel.Unknown]: { label: "위험도 판단 불가", filledCount: 0, barColorClass: "", textColorClass: "text-neutral-muted" },
};

const BAR_HEIGHT_CLASSES = ["h-1.5", "h-2.5", "h-3.5"];

interface RiskMeterProps {
    riskLevel: RiskLevel
}

function RiskMeter({ riskLevel }: RiskMeterProps) {
    const style = RISK_METER_STYLE[riskLevel];
    const isUnknown = riskLevel === RiskLevel.Unknown;

    return (
        <div className="flex items-center gap-1.5">
            <div className="flex items-end gap-0.5" aria-hidden="true">
                {BAR_HEIGHT_CLASSES.map((heightClass, index) => (
                    <div
                        key={heightClass}
                        className={cn(
                            "w-1.25 rounded-[1px]",
                            heightClass,
                            isUnknown
                                ? "border border-dashed border-neutral-border"
                                : index < style.filledCount ? style.barColorClass : "bg-neutral-border/40",
                        )}
                    />
                ))}
            </div>
            <p className={cn("text-sm font-semibold", style.textColorClass)}>{style.label}</p>
        </div>
    );
}

export default RiskMeter;
