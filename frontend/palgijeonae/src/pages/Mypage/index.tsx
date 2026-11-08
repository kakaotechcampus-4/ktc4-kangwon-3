import { useRef, useState } from "react";

// TODO: API 미구현 기능(RevisionNoticeBanner)에서만 쓰는 import. 추후 구현 시 주석을 해제할 것.
// import { ResultStatus } from "@/api/types/common.ts";
import SectionIntro from "@/components/common/SectionIntro";
import MyProductList from "@/pages/Mypage/components/MyProductList.tsx";
import NotificationSettings from "@/pages/Mypage/components/NotificationSettings.tsx";
import ProductFilterBar from "@/pages/Mypage/components/ProductFilterBar.tsx";
import ProfileSection from "@/pages/Mypage/components/ProfileSection.tsx";
import WithdrawSection from "@/pages/Mypage/components/WithdrawSection.tsx";
import { useMyProducts } from "@/pages/Mypage/hooks/useMyProducts.ts";

import { PAGE_SIZE } from "./constants.ts";
// TODO: API 미구현 기능. 추후 구현 시 주석을 해제할 것.
// import RevisionNoticeBanner from "@/pages/Mypage/components/RevisionNoticeBanner.tsx";
import type { ProductFilter } from "./types.ts";

function MyPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [page, setPage] = useState(0);
    const productListRef = useRef<HTMLDivElement>(null);

    const { data, isPending, isError, refetch } = useMyProducts(filter, searchTerm, page);

    // 렌더링 시 type error / Pagination 크래시 방지용 빈 데이터 배열과 빈 페이지 정보.
    const pagedProducts = data?.items ?? [];
    const pageInfo = data?.pageInfo ?? { page, size: PAGE_SIZE, totalElements: 0, totalPages: 1, hasNext: false };

    // 상품 검색어 / 필터가 변경되면 페이지 범위가 달라지므로 처음(0)으로 설정
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
            {/* TODO: API 미구현 기능. 추후 구현 시 주석을 해제할 것. */}
            {/* <RevisionNoticeBanner
                revisedDate="2026-09-03"
                title="어린이제품 안전 특별법 시행규칙 별표2가 개정되었습니다. 완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다."
                description="사입으로 등록한 상품 1개는 재확인이 필요합니다. 구매대행 상품은 이 조문의 적용을 받지 않아 영향이 없습니다."
                onCheckClick={() => {
                    handleFilterChange(ResultStatus.RecheckRequired);
                    productListRef.current?.scrollIntoView({ behavior: "smooth" });
                }}
            /> */}
            <ProfileSection />
            <NotificationSettings />
            <ProductFilterBar
                searchTerm={searchTerm}
                onSearchTermChange={handleSearchTermChange}
                filter={filter}
                onFilterChange={handleFilterChange}
            />
            <div ref={productListRef}>
                <MyProductList
                    products={pagedProducts}
                    isLoading={isPending}
                    isError={isError}
                    onRetry={refetch}
                    page={page}
                    totalPages={pageInfo.totalPages}
                    hasNext={pageInfo.hasNext}
                    onPageChange={setPage}
                    onProductDeleted={(wasLastOnPage) => {
                        if (wasLastOnPage && page > 0) {
                            setPage(page - 1);
                        }
                    }}
                />
            </div>
            <WithdrawSection />
        </div>
    );
}

export default MyPage;
