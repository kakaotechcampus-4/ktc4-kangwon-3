import { useMemo, useState } from "react";

import { getMyProducts } from "@/api/myProducts.ts";
import SectionIntro from "@/components/common/SectionIntro";

import MyProductList from "./MyProductList.tsx";
import NotificationSettings from "./NotificationSettings.tsx";
import ProductFilterBar from "./ProductFilterBar.tsx";
import RevisionNoticeBanner from "./RevisionNoticeBanner.tsx";
import type { ProductFilter } from "./types.ts";

// TODO: 실제 연동 시 백엔드 페이지네이션(page/size)으로 교체.
// 지금은 목업 확인용으로 2로 설정.
const PAGE_SIZE = 2;

function MyPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [page, setPage] = useState(0);

    const { items: pagedProducts, totalPages } = useMemo(
        () => getMyProducts({
            resultStatus: filter === "all" ? undefined : filter,
            keyword: searchTerm,
            page: page,
            size: PAGE_SIZE,
            sortType: "LATEST",
        }),
        [searchTerm, filter, page],
    );

    // 검색어 / 필터가 변경되면 페이지 범위가 달라지므로 처음(0)으로 설정
    const handleSearchTermChange = (value: string) => {
        setSearchTerm(value);
        setPage(0);
    };

    const handleFilterChange = (value: ProductFilter) => {
        setFilter(value);
        setPage(0);
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="마이페이지" description="지금까지 진단한 상품들을 확인할 수 있어요" />
            <RevisionNoticeBanner
                revisedDate="2026-09-03"
                title="어린이제품 안전 특별법 시행규칙 별표2가 개정되었습니다. 완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다."
                description="사입으로 등록한 상품 1개는 재확인이 필요합니다. 구매대행 상품은 이 조문의 적용을 받지 않아 영향이 없습니다."
                onCheckClick={() => handleFilterChange("RECHECK_REQUIRED")}
            />
            <NotificationSettings />
            <ProductFilterBar
                searchTerm={searchTerm}
                onSearchTermChange={handleSearchTermChange}
                filter={filter}
                onFilterChange={handleFilterChange}
            />
            <MyProductList
                products={pagedProducts}
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
            />
        </div>
    );
}

export default MyPage;
