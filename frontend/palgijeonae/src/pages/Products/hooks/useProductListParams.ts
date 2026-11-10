import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

import type { SortType } from "@/api/products.ts";
import type { ProductFilter } from "@/pages/Products/types.ts";
import { type ListParams, parseListParams, toSearchParams } from "@/pages/Products/utils/listParams.ts";

// 목록 조건(필터·검색어·정렬·페이지)을 주소 쿼리에서 읽고 쓴다.
// 조건을 바꾸면 새 기록으로 이동해 브라우저 뒤로 가기로 이전 조건에 돌아갈 수 있다.
export function useProductListParams() {
    const [searchParams, setSearchParams] = useSearchParams();
    const params = parseListParams(searchParams);

    const update = (next: Partial<ListParams>, replace = false) => {
        const nextSearchParams = toSearchParams({ ...params, ...next });
        // 같은 조건을 다시 고르면(같은 검색어로 Enter 등) 같은 기록이 쌓이지 않게 한다.
        if (nextSearchParams.toString() === searchParams.toString()) {
            return;
        }
        setSearchParams(nextSearchParams, { replace });
    };

    // 없는 페이지를 고칠 때처럼 기록을 남기지 않고 주소만 바꾼다.
    const replacePage = useCallback(
        (page: number) => setSearchParams(toSearchParams({ ...parseListParams(searchParams), page }), { replace: true }),
        [searchParams, setSearchParams],
    );

    return {
        ...params,
        // 필터·검색어·정렬이 바뀌면 페이지 범위가 달라지므로 첫 페이지로 되돌린다.
        setFilter: (filter: ProductFilter) => update({ filter, page: 0 }),
        setKeyword: (keyword: string) => update({ keyword, page: 0 }),
        setSortType: (sortType: SortType) => update({ sortType, page: 0 }),
        setPage: (page: number) => update({ page }),
        replacePage,
    };
}
