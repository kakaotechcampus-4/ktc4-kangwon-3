import type { ProductResult } from "@/api/product";

import apiClient from "./client";

/** 상품 단건 조회 */
export async function getProduct(productId: string) {
    const response = await apiClient.get(`/api/v1/products/${productId}`);
    return response.data.data as ProductResult;
}

/** 진단서 조회 (진단서 단위, 여러 상품 결과를 한 번에 조회) */
export const getDiagnosesDetail = async (diagnosesId: string) => {
    const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    return response.data.data.products as ProductResult[];
};

/** 실패한 상품을 같은 진단서(diagnosesId) 안에서 다시 진단한다. */
export async function retryDiagnosis(productId: string): Promise<void> {
    await apiClient.post(`/api/v1/products/${productId}/retry`);
}
