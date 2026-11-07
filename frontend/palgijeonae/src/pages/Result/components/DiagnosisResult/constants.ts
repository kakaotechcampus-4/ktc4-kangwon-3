import { Determination, ToolName } from "@/api/product";

// 진단 결과를 검토한 규제 분야 라벨.
export const TOOL_NAME_LABELS: Record<ToolName, string> = {
    [ToolName.Customs]: "통관",
    [ToolName.Children]: "어린이 제품",
    [ToolName.Electrical]: "전기 안전",
    [ToolName.Radio]: "전파",
    [ToolName.FoodDrug]: "식품·의약품",
    [ToolName.LabelAd]: "표시·광고",
};

// 판정 결과에 따른 라벨.
export const DETERMINATION_LABELS: Record<Determination, string> = {
    [Determination.Required]: "조치 필요",
    [Determination.PossiblyRequired]: "확인 필요",
    [Determination.InsufficientInformation]: "정보 부족",
    [Determination.NotRequired]: "통과",
    [Determination.NotApplicable]: "해당 없음",
};

// 판정 결과 라벨에 대한 한 줄 설명. 필터 안내 툴팁에서 사용
export const DETERMINATION_DESCRIPTIONS: Record<Determination, string> = {
    [Determination.Required]: "인증·신고 등 이 규제에 따른 조치를 반드시 진행해야 해요",
    [Determination.PossiblyRequired]: "상품 정보만으로는 확정할 수 없어 추가 확인이 필요해요",
    [Determination.InsufficientInformation]: "상세페이지 정보가 부족해 AI가 판단하지 못했어요",
    [Determination.NotRequired]: "현재 상품 조건에서는 별도 조치 없이 판매할 수 있어요",
    [Determination.NotApplicable]: "이 상품은 해당 규제의 적용 대상이 아니에요",
};

// 필터 안내 툴팁에 보여줄 순서
export const DETERMINATION_LEGEND_ORDER: Determination[] = [
    Determination.Required,
    Determination.PossiblyRequired,
    Determination.NotRequired,
    Determination.InsufficientInformation,
    Determination.NotApplicable,
];
