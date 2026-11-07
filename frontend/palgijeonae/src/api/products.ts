import apiClient from "@/api/core/client";
import type { ResultStatus } from "@/api/types/common";
import type { ProductResult } from "@/api/types/product";
import type { MyProductItem, PageInfo } from "@/pages/Mypage/types";
import type { AnswerSubmission } from "@/pages/Question/types";

export enum SortType {
    Latest = "LATEST",
    Oldest = "OLDEST",
}

interface GetMyProductsParams {
    resultStatus?: ResultStatus;
    keyword?: string;
    page: number;
    size: number;
    sortType: SortType;
}

export async function getMyProducts(params: GetMyProductsParams) {
    const response = await apiClient.get("/api/v1/products", {
        params: {
            resultStatus: params.resultStatus,
            keyword: params.keyword || undefined,
            page: params.page,
            size: params.size,
            sortType: params.sortType,
        },
    });

    const { products, pageInfo } = response.data.data as { products: MyProductItem[]; pageInfo: PageInfo };
    return { items: products, pageInfo };
}

/** 상품 단건 조회 */
export async function getProduct(productId: string) {
    const response = await apiClient.get(`/api/v1/products/${productId}`);
    return response.data.data as ProductResult;
}

/** 상품 단건 삭제. 진단서에 남은 상품이 없으면 진단서도 함께 삭제된다. */
export async function deleteProduct(productId: string) {
    await apiClient.delete(`/api/v1/products/${productId}`);
}

/**
 * 답변을 제출한다. 제출하면 상품은 다시 진행 중(IN_PROGRESS)이 되고, 이어진 진단에서 질문이 한 번 더 올 수 있다(최대 2회차).
 * @param productId 답변을 제출할 상품 id
 * @param answers 지금 기다리는 회차의 질문 전체에 대한 답변 목록
 */
export async function submitAnswers(productId: string, answers: AnswerSubmission[]): Promise<void> {
    await apiClient.post(`/api/v1/products/${productId}/answers`, { answers });
}

/** 실패한 상품을 같은 진단서(diagnosesId) 안에서 다시 진단한다. */
export async function retryDiagnosis(productId: string): Promise<void> {
    await apiClient.post(`/api/v1/products/${productId}/retry`);
}
