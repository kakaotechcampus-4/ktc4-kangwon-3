import { useMemo, useState } from "react";

import SectionIntro from "@/components/common/SectionIntro";

import MyProductList from "./MyProductList.tsx";
import NotificationSettings from "./NotificationSettings.tsx";
import ProductFilterBar from "./ProductFilterBar.tsx";
import RevisionNoticeBanner from "./RevisionNoticeBanner.tsx";
import type { MyProductItem, ProductFilter } from "./types.ts";

// TODO: 실제 연동 시 백엔드 페이지네이션(page/size)으로 교체. 지금은 목업 개수가 적어 페이지당 2개로 작게 잡아 UI만 미리 확인한다.
const PAGE_SIZE = 2;

// TODO: 백엔드 연동 전까지 쓰는 임시 목업. 실제 연동은 별도 브랜치에서 진행 예정(검색 파라미터 등 백엔드 작업 필요).
const PRODUCTS: MyProductItem[] = [
    {
        id: 1,
        title: "오이 모양 크런치 말랑이",
        inputType: "url",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        link: "https://example.com/product/1",
    },
    {
        id: 2,
        title: "유아용 사이즈 딸기 무늬 신발",
        inputType: "text",
        resultStatus: "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
        content: "유아용 신발, 사이즈 130, 딸기 무늬",
    },
    {
        id: 3,
        title: "팔찌 만들기 DIY용 야광 비즈 5색",
        inputType: "image",
        resultStatus: "RECHECK_REQUIRED",
        images: [],
    },
    {
        id: 4,
        title: "강아지 겨울용 니트 조끼",
        inputType: "url",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        link: "https://example.com/product/4",
    },
    {
        id: 5,
        title: "실리콘 유아 식판 세트",
        inputType: "text",
        resultStatus: "RECHECK_REQUIRED",
        content: "실리콘 재질, BPA free, 유아용 식판",
    },
];

function MyPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [page, setPage] = useState(0);

    const filteredProducts = useMemo(() => {
        const trimmed = searchTerm.trim();
        return PRODUCTS
            .filter((product) => filter === "all" || product.resultStatus === filter)
            .filter((product) => product.title.includes(trimmed));
    }, [searchTerm, filter]);

    const totalPages = Math.max(Math.ceil(filteredProducts.length / PAGE_SIZE), 1);
    const pagedProducts = filteredProducts.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

    // 검색어/필터가 바뀌면 이전 페이지 번호가 새 결과 범위를 벗어날 수 있어, 그 시점에 같이 0으로 되돌린다.
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
