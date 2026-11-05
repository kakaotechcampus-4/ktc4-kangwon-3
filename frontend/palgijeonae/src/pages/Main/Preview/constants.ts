import type { ComponentType } from "react";

import JudgementSlide from "./slides/JudgementSlide";
import QuestionSlide from "./slides/QuestionSlide";
import ResultSlide from "./slides/ResultSlide";
import UploadSlide from "./slides/UploadSlide";

// 슬라이드 한 장이 자동 전환되기까지 걸리는 시간.
export const PREVIEW_DURATION = "10s";

export interface PreviewSlideInfo {
    key: string
    label: string
    caption: string
    Component: ComponentType
}

export const PREVIEW_SLIDES: PreviewSlideInfo[] = [
    { key: "upload", label: "상품 업로드", caption: "URL이나 텍스트·이미지로 최대 10개까지 담아요.", Component: UploadSlide },
    { key: "judgement", label: "진단 진행", caption: "여러 상품을 동시에 진단하고 단계별 진행 상황을 보여줘요.", Component: JudgementSlide },
    { key: "question", label: "질문 답변", caption: "판단이 어려운 부분만 질문해요. 답하면 바로 이어서 진단해요.", Component: QuestionSlide },
    { key: "result", label: "진단 결과", caption: "판정과 근거 법령, 판매 전에 해야 할 일을 확인해요.", Component: ResultSlide },
];
