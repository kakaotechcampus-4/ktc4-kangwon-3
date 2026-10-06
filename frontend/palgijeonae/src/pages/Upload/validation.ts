import {
    ALLOWED_IMAGE_EXTENSIONS_LABEL,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    MAX_PRODUCT_IMAGE_COUNT,
    MAX_PRODUCT_NAME_LENGTH,
} from "./constraints.ts";
import type { Product } from "./types.ts";

// 상품 추가 / 제출 직전에 사용하는 상품 공용 검증.
export const isAllowedImageType = (file: File): boolean => ALLOWED_IMAGE_MIME_TYPES.includes(file.type);
export const isWithinFileSizeLimit = (file: File): boolean => file.size <= MAX_FILE_SIZE_BYTES;

// 이미지 형식/크기에 대한 검증
export const validateImageFile = (file: File): string | null => {
    if (!isAllowedImageType(file)) {
        return `${ALLOWED_IMAGE_EXTENSIONS_LABEL} 형식의 이미지만 첨부할 수 있습니다.`;
    }
    if (!isWithinFileSizeLimit(file)) {
        return `이미지는 1장당 ${MAX_FILE_SIZE_MB}MB까지만 첨부할 수 있습니다.`;
    }
    return null;
};

// 글자수, 개수, 입력 관련 검증
export const validateProduct = (product: Product): string | null => {
    if (!product.title.trim()) {
        return "제품명을 입력해주세요.";
    }
    if (product.title.length > MAX_PRODUCT_NAME_LENGTH) {
        return `제품명은 ${MAX_PRODUCT_NAME_LENGTH}자를 넘을 수 없습니다.`;
    }

    if (product.productImageFile) {
        const thumbnailError = validateImageFile(product.productImageFile);
        if (thumbnailError) {
            return thumbnailError;
        }
    }

    if (product.type === "url") {
        return product.link?.trim() ? null : "상세페이지 링크를 입력해주세요.";
    }

    const hasContent = Boolean(product.content?.trim());
    const hasImages = (product.images?.length ?? 0) > 0;
    if (!hasContent && !hasImages) {
        return "상세페이지 내용이나 이미지를 입력해주세요.";
    }

    if ((product.images?.length ?? 0) > MAX_PRODUCT_IMAGE_COUNT) {
        return `이미지는 최대 ${MAX_PRODUCT_IMAGE_COUNT}장까지 첨부할 수 있습니다.`;
    }

    const invalidImage = product.images?.map(validateImageFile).find((error) => error !== null);
    return invalidImage ?? null;
};
