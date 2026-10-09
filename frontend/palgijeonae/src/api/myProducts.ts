import type { MyProductItem, PageInfo, ResultStatus } from "@/pages/Mypage/types";

import apiClient from "./client";

interface GetMyProductsParams {
    resultStatus?: ResultStatus;
    keyword?: string;
    page: number;
    size: number;
    sortType: "LATEST" | "OLDEST";
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
