import {
    postDiagnosis,
    type PresignedFileType,
    putToS3,
    requestPresignedUrls,
} from "@/api/diagnosis";

import type { DiagnosisProductPayload, Product } from "./types.ts";

interface ProductImageKeys {
    productImageKey?: string
    imageKeys: string[]
}

// 대표 이미지(있다면 항상 0번)와 상세 이미지들을 한 배치로 요청하고, 응답을 요청과 같은 순서로 매칭한다.
export const uploadProductImages = async (product: Product): Promise<ProductImageKeys> => {
    const mainFile = product.productImageFile;
    const detailFiles = product.type === "text/image" ? product.images ?? [] : [];
    // mainFile(썸네일)이 있다면 썸네일이 0번, 없다면 바로 상세 페이지 이미지가 0번
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

    if (presignedFiles.length !== files.length) {
        throw new Error("발급받은 presigned URL 개수가 요청한 파일 개수와 다릅니다.");
    }

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

// sourceType(url/text-image)에 따라 필드를 분기하여 Product를 DiagnosisProductPayload로 재구성한다.
export const buildDiagnosisPayload = (product: Product, keys: ProductImageKeys): DiagnosisProductPayload => {
    const base = { productName: product.title, productImageKey: keys.productImageKey };

    return product.type === "url"
        ? { ...base, sourceType: "URL", sourceUrl: product.link }
        : { ...base, sourceType: "TEXT_IMAGE", sourceText: product.content, imageKeys: keys.imageKeys };
};

// 상품 배열 전체를 업로드 → 페이로드 조립 → 한 번의 진단 요청으로 제출하는 전체 파이프라인
export const submitDiagnosis = async (products: Product[]): Promise<string> => {
    const results = await Promise.allSettled(
        products.map(async (product) => {
            const keys = await uploadProductImages(product);
            return buildDiagnosisPayload(product, keys);
        }),
    );

    const failedProductNames = products
        .filter((_, index) => results[index].status === "rejected")
        .map((product) => product.title);

    if (failedProductNames.length > 0) {
        throw new Error(`다음 상품의 이미지 업로드에 실패했습니다: ${failedProductNames.join(", ")}`);
    }

    const payloads = (results as PromiseFulfilledResult<DiagnosisProductPayload>[]).map((result) => result.value);
    return postDiagnosis(payloads);
};

