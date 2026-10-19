import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";
import imageIcon from "@/assets/upload-img_txt.svg";
import urlIcon from "@/assets/upload-url.svg";

export interface Badge {
    label: string
    className: string
}

export interface SourceTypeInfo {
    icon: string
    label: string
}

// 진단이 끝난 상품의 배지.
export const RESULT_STATUS_BADGES: Record<ResultStatus, Badge> = {
    [ResultStatus.PurchasingAgentAllowed]: { label: "구매 대행 가능", className: "text-status-success bg-status-success-bg" },
    [ResultStatus.DirectImportCertificationRequired]: { label: "사입 인증 필요", className: "text-status-danger bg-status-danger-bg" },
    [ResultStatus.RecheckRequired]: { label: "재확인 필요", className: "text-status-warning bg-status-warning-bg" },
};

// 진단이 끝나지 않은 상품의 배지.
export const PROCESSING_STATUS_BADGES: Partial<Record<ProcessingStatusType, Badge>> = {
    [ProcessingStatusType.Pending]: { label: "대기 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.InProgress]: { label: "진단 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.AwaitingInput]: { label: "입력 대기 중", className: "text-neutral-border bg-white" },
    [ProcessingStatusType.Failed]: { label: "진단 실패", className: "text-status-danger bg-status-danger-bg" },
};

// 진단이 끝났지만 결과 상태가 없는 상품(오류)일 경우의 배지
export const FALLBACK_BADGE: Badge = { label: "확인 중", className: "text-neutral-border bg-white" };

// 상품 등록 방식(URL/텍스트-이미지) 아이콘/라벨.
export const SOURCE_TYPE_INFO: Record<SourceType, SourceTypeInfo> = {
    [SourceType.Url]: { icon: urlIcon, label: "URL" },
    [SourceType.TextImage]: { icon: imageIcon, label: "이미지 / 텍스트" },
};
