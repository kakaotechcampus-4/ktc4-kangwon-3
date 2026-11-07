import apiClient from "@/api/core/client";
import type { DiagnosesDetail, ProductResult } from "@/api/types/product";
import type { DiagnosisProductPayload } from "@/pages/Upload/types";

// 상품 배열을 한 번에 진단 요청한다.
export const postDiagnosis = async (products: DiagnosisProductPayload[]): Promise<string> => {
    const response = await apiClient.post("/api/v1/diagnoses", { products });
    return response.data.data.diagnosesId;
};

/** 진단서 조회 (진단서 단위, 여러 상품 결과를 한 번에 조회) */
export const getDiagnosesDetail = async (diagnosesId: string) => {
    const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    return response.data.data.products as ProductResult[];
};

export async function getDiagnosesPolling(diagnosesId: string) {
    const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    return response.data.data as DiagnosesDetail;
}
