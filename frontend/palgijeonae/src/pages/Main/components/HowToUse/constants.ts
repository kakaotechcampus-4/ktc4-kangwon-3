import type { ComponentType } from "react";

import JudgementStepPreview from "@/pages/Main/components/HowToUse/components/JudgementStepPreview";
import QuestionStepPreview from "@/pages/Main/components/HowToUse/components/QuestionStepPreview";
import ResultStepPreview from "@/pages/Main/components/HowToUse/components/ResultStepPreview";
import UploadStepPreview from "@/pages/Main/components/HowToUse/components/UploadStepPreview";

export interface HowToUseStepInfo {
    key: string
    title: string
    tag?: string
    description: string
    tips: string[]
    Preview: ComponentType
}

export const HOW_TO_USE_STEPS: HowToUseStepInfo[] = [
    {
        key: "upload",
        title: "상품 담기",
        description: "판매 페이지 링크로 담거나, 링크가 안 열리는 상품은 상세페이지 텍스트·이미지로 담아요.",
        tips: [
            "한 번에 최대 10개까지 담을 수 있어요",
            "캡처 이미지는 상품당 최대 20장, 화면을 확대해서 캡처하면 글자를 더 정확하게 인식해요",
        ],
        Preview: UploadStepPreview,
    },
    {
        key: "judgement",
        title: "진단 진행",
        description: "상세페이지 읽기 → 검토 분야 선택 → 법령 검토 → 정리·검증 순서로 진행되고, 담은 상품이 동시에 진행돼요.",
        tips: [
            "화면을 떠났다면 진단 결과 → 진행 중인 상품 클릭 → 배너의 ‘진행 상황 확인’ 버튼으로 다시 돌아와요",
            "진단이 끝난 상품은 다른 상품을 기다리지 않고 바로 결과를 확인할 수 있어요.",
        ],
        Preview: JudgementStepPreview,
    },
    {
        key: "question",
        title: "질문 답변",
        tag: "정보가 부족할 경우",
        description: "상세페이지만으로 판단하기에 정보가 부족하면 질문이 생겨요. 답하면 바로 이어서 진단해요.",
        tips: ["답은 자유롭게 쓰면 AI가 분석해요", "답한 내용은 진단서에 반영돼요"],
        Preview: QuestionStepPreview,
    },
    {
        key: "result",
        title: "결과 확인",
        description: "진단 결과·다음 단계·상품 정보 탭에서 판정과 근거, 해야 할 일을 확인해요.",
        tips: [
            "상품마다 사입 가능 · 사입 인증 필요 · 재확인 필요로 판정해요",
            "해야 할 일을 순서대로 정리해 드려요",
        ],
        Preview: ResultStepPreview,
    },
];
