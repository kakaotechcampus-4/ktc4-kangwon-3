import type { ResultStatus } from "@/api/types";
import type { MyProductItem, PageInfo } from "@/pages/Mypage/types";

import apiClient from "./client";

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

/** 상품 단건 삭제. 진단서에 남은 상품이 없으면 진단서도 함께 삭제된다. */
export async function deleteProduct(productId: string) {
    await apiClient.delete(`/api/v1/products/${productId}`);
}
