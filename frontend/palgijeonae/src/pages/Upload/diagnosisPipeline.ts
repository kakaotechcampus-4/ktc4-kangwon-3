import {
    createDiagnosis,
    type DiagnosisCreatePayload,
    type PresignedFileType,
    putToS3,
    requestPresignedUrls,
} from "@/api/diagnosis";

import type { Product } from "./types.ts";

interface ProductImageKeys {
    productImageKey?: string
    imageKeys: string[]
}

// 대표 이미지(있다면 항상 0번)와 상세 이미지들을 한 배치로 요청하고, 응답을 요청과 같은 순서로 매칭한다.
// presigned 응답엔 인덱스가 없고 파일명은 중복될 수 있어 이름으로 매칭하면 안 된다.
export const uploadProductImages = async (product: Product): Promise<ProductImageKeys> => {
    const mainFile = product.productImageFile;
    const detailFiles = product.type === "text/image" ? product.images ?? [] : [];
    const files = mainFile ? [mainFile, ...detailFiles] : detailFiles;

    if (files.length === 0) {
        return { productImageKey: undefined, imageKeys: [] };
    }

    // presigned URL 발급 요청
    const presignedFiles = await requestPresignedUrls(
        files.map((file, index) => ({
            type: (mainFile && index === 0 ? "PRODUCT_MAIN" : "PRODUCT_DETAIL") as PresignedFileType,
            fileName: file.name,
            fileSize: file.size,
        })),
    );

    // 발급받은 presigned URL로 각 파일을 S3에 업로드
    await Promise.all(
        files.map((file, index) => putToS3(presignedFiles[index].presignedUrl, file, presignedFiles[index].contentType)),
    );

    // 대표 이미지가 있었다면 0번 key가 productImageKey, 나머지가 imageKeys
    const keys = presignedFiles.map((presignedFile) => presignedFile.key);
    return mainFile
        ? { productImageKey: keys[0], imageKeys: keys.slice(1) }
        : { productImageKey: undefined, imageKeys: keys };
};

// sourceType(url/text-image)에 따라 diagnoses 요청 필드를 분기해서 조립
export const buildDiagnosisPayload = (product: Product, keys: ProductImageKeys): DiagnosisCreatePayload => {
    const base = { productName: product.title, productImageKey: keys.productImageKey };

    return product.type === "url"
        ? { ...base, sourceType: "URL", sourceUrl: product.link }
        : { ...base, sourceType: "TEXT_IMAGE", sourceText: product.content, imageKeys: keys.imageKeys };
};

// 상품 1개를 업로드→진단 생성까지 처리하는 전체 파이프라인
export const processProduct = async (product: Product): Promise<number> => {
    const keys = await uploadProductImages(product);
    return createDiagnosis(buildDiagnosisPayload(product, keys));
};
