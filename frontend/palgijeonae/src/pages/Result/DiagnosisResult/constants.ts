import { Determination, ToolName } from "@/api/product";

// 진단 결과를 검토한 규제 분야 라벨.
export const TOOL_NAME_LABELS: Record<ToolName, string> = {
    [ToolName.Customs]: "통관",
    [ToolName.Children]: "어린이 제품",
    [ToolName.Electrical]: "전기 안전",
    [ToolName.Radio]: "전파",
    [ToolName.FoodDrug]: "식약",
    [ToolName.LabelAd]: "표시 광고",
};

export interface DeterminationStyle {
    label: string
    className: string
}

// 판정 결과별 라벨/색
export const DETERMINATION_STYLE: Record<Determination, DeterminationStyle> = {
    [Determination.Required]: { label: "조치 필요", className: "text-status-danger bg-status-danger-bg border-status-danger" },
    [Determination.PossiblyRequired]: { label: "확인 필요", className: "text-status-warning bg-status-warning-bg border-status-warning" },
    [Determination.InsufficientInformation]: { label: "정보 부족", className: "text-neutral-dark bg-white border-neutral-border" },
    [Determination.NotRequired]: { label: "통과", className: "text-status-success bg-status-success-bg border-status-success" },
    [Determination.NotApplicable]: { label: "해당 없음", className: "text-status-success bg-status-success-bg border-status-success" },
};
