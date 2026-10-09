import { useQuery } from "@tanstack/react-query";

import { getMyProducts } from "@/api/myProducts.ts";

import type { ProductFilter } from "./types.ts";

// 한 페이지에 보여줄 상품 개수
export const PAGE_SIZE = 10;

// 상품 목록 조회.
export function useMyProducts(filter: ProductFilter, searchTerm: string, page: number) {
    return useQuery({
        queryKey: ["myProducts", { filter, searchTerm, page, size: PAGE_SIZE }],
        queryFn: () => getMyProducts({
            resultStatus: filter === "all" ? undefined : filter,
            keyword: searchTerm,
            page,
            size: PAGE_SIZE,
            sortType: "LATEST",
        }),
    });
}
