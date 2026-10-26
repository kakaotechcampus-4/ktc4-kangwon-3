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

// 판정 결과에 따른 라벨.
export const DETERMINATION_LABELS: Record<Determination, string> = {
    [Determination.Required]: "조치 필요",
    [Determination.PossiblyRequired]: "확인 필요",
    [Determination.InsufficientInformation]: "정보 부족",
    [Determination.NotRequired]: "통과",
    [Determination.NotApplicable]: "해당 없음",
};
