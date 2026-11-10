import { SortType } from "@/api/products.ts";
import { ResultStatus } from "@/api/types/common.ts";
import type { ProductFilter } from "@/pages/Products/types.ts";

// 목록 조건을 담는 주소 쿼리 이름.
export const LIST_PARAM_KEYS = {
    status: "status",
    keyword: "keyword",
    sort: "sort",
    page: "page",
} as const;

// 백엔드 page가 Java int라서, 이보다 큰 값을 보내면 400이 나 없는 페이지 보정도 할 수 없다.
export const MAX_PAGE_PARAM = 2147483647;

export interface ListParams {
    filter: ProductFilter
    keyword: string
    sortType: SortType
    // API·컴포넌트와 같이 0부터 센 값. 주소에서는 1부터 센다.
    page: number
}

// 정해진 값이 아니면 기본값으로 읽는다. 주소를 고쳐 쓰지는 않는다.
export function parseListParams(searchParams: URLSearchParams): ListParams {
    const status = searchParams.get(LIST_PARAM_KEYS.status);
    const sort = searchParams.get(LIST_PARAM_KEYS.sort);
    const pageParam = searchParams.get(LIST_PARAM_KEYS.page);

    const filter = Object.values(ResultStatus).find((value) => value === status) ?? "all";
    const sortType = Object.values(SortType).find((value) => value === sort) ?? SortType.Latest;
    // Number()는 "2e3", "0x10", " 3", "1.5"도 숫자로 읽으므로 숫자만으로 된 문자열만 받는다.
    const pageNumber = pageParam !== null && /^\d+$/.test(pageParam) ? Number(pageParam) : 0;
    const page = pageNumber >= 1 && pageNumber <= MAX_PAGE_PARAM ? pageNumber - 1 : 0;

    return { filter, keyword: searchParams.get(LIST_PARAM_KEYS.keyword) ?? "", sortType, page };
}

// 기본값은 쓰지 않아서, 조건이 모두 기본이면 쿼리가 비어 있다.
export function toSearchParams({ filter, keyword, sortType, page }: ListParams): URLSearchParams {
    const searchParams = new URLSearchParams();
    if (filter !== "all") {
        searchParams.set(LIST_PARAM_KEYS.status, filter);
    }
    if (keyword !== "") {
        searchParams.set(LIST_PARAM_KEYS.keyword, keyword);
    }
    if (sortType !== SortType.Latest) {
        searchParams.set(LIST_PARAM_KEYS.sort, sortType);
    }
    if (page > 0) {
        searchParams.set(LIST_PARAM_KEYS.page, String(page + 1));
    }
    return searchParams;
}

// 페이지가 0개여도 첫 페이지(0)는 있는 것으로 본다.
export function getLastPageIndex(totalPages: number): number {
    return Math.max(totalPages, 1) - 1;
}
