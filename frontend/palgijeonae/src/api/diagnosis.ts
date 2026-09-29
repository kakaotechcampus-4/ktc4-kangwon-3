import axios from "axios";

import type { DiagnosisProductPayload } from "@/pages/Upload/types";

import apiClient from "./client";

// 업로드, 재진단 등 여러 화면에서 공통으로 사용하기 위함
export type PresignedFileType = "PRODUCT_MAIN" | "PRODUCT_DETAIL";

interface PresignedFileRequest {
    type: PresignedFileType
    fileName: string
    fileSize: number
}

export interface PresignedFile {
    fileName: string
    key: string
    presignedUrl: string
    contentType: string
}

// S3에 직접 파일을 업로드할 수 있도록 presigned url을 요청하는 함수
export const requestPresignedUrls = async (files: PresignedFileRequest[]): Promise<PresignedFile[]> => {
    const response = await apiClient.post("/api/v1/presigned-url", { files });
    return response.data.data.files;
};

// presigned PUT은 S3로 직접 나가야 해서, Authorization 헤더를 자동으로 붙이지 않도록 client와 따로 구현
export const putToS3 = (presignedUrl: string, file: File, contentType: string) =>
    axios.put(presignedUrl, file, { headers: { "Content-Type": contentType } });

// 상품 배열을 한 번에 진단 요청으로 등록한다.
export const postDiagnosis = async (products: DiagnosisProductPayload[]): Promise<string> => {
    const response = await apiClient.post("/api/v1/diagnoses", { products });
    return response.data.data.diagnosesId;
};