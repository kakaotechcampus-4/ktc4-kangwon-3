import { SortType } from "@/api/products.ts";

// 한 번에 불러올 상품 개수
export const PAGE_SIZE = 10;

// 페이지네이션에서 한 화면에 보여줄 페이지 번호 버튼 개수
export const PAGE_GROUP_SIZE = 10;
export const PAGE_GROUP_SIZE_MOBILE = 5;

// 목록 정렬 선택지. 화면에 보이는 순서대로 둔다.
export const SORT_OPTIONS: { type: SortType; label: string }[] = [
    { type: SortType.Latest, label: "최신순" },
    { type: SortType.Oldest, label: "오래된순" },
];

// 법령 개정 알림 쿼리 키. 재진단·삭제·알림 설정이 바뀌면 이 키를 무효화해 배너를 갱신한다.
export const LAW_AMENDMENTS_QUERY_KEY = ["lawAmendments"];
