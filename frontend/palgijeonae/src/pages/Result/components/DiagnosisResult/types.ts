import type { Determination } from "@/api/product";

// null은 "전체"(필터 없음)를 의미한다.
export type FindingFilter = Determination | null;
