import apiClient from "@/api/core/client";
import type { ToolName } from "@/api/types/product";

/** 개정 때문에 다시 진단할 수 있는 상품 */
export interface RecheckProduct {
    productId: string
    // 재진단 뒤 진행 화면(/judgement/:diagnosesId)으로 이동할 때 쓴다.
    diagnosesId: string
    productName: string
}

export interface LawAmendment {
    lawAmendmentId: string
    lawName: string
    // 개정 종류(일부개정 등)를 알 수 없으면 null이다.
    revisionType: string | null
    toolName: ToolName
    // 시행일이 정해지지 않았으면 null이다.
    enforceDate: string | null
    products: RecheckProduct[]
}

/** 법령 개정 알림 조회. 알림 수신을 끈 회원은 빈 목록을 받는다. */
export async function getLawAmendments(): Promise<LawAmendment[]> {
    const response = await apiClient.get("/api/v1/law-amendments");
    return (response.data.data as { lawAmendments: LawAmendment[] }).lawAmendments;
}
