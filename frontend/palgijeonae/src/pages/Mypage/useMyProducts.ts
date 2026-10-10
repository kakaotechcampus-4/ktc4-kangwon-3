import { useQuery } from "@tanstack/react-query";

import { getMyProducts } from "@/api/myProducts.ts";

import { PAGE_SIZE } from "./constraints.ts";
import type { ProductFilter } from "./types.ts";

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
