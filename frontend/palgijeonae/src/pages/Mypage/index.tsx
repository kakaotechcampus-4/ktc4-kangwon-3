import { useMemo, useState } from "react";

import SectionIntro from "@/components/common/SectionIntro";

import MyProductList from "./MyProductList.tsx";
import NotificationSettings from "./NotificationSettings.tsx";
import ProductFilterBar from "./ProductFilterBar.tsx";
import RevisionNoticeBanner from "./RevisionNoticeBanner.tsx";
import type { MyProductItem, ProductFilter } from "./types.ts";

// TODO: 실제 연동 시 백엔드 페이지네이션(page/size)으로 교체.
// 지금은 목업 확인용으로 2로 설정.
const PAGE_SIZE = 2;

// TODO: 백엔드 연동 전까지 쓰는 임시 목업. 
// 실제 연동은 별도 브랜치에서 진행
const PRODUCTS: MyProductItem[] = [
    {
        productId: 1,
        productName: "오이 모양 크런치 말랑이",
        sourceType: "URL",
        inputType: "url",
        processingStatus: "COMPLETE",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        createdAt: new Date("2026-09-01"),
    },
    {
        productId: 2,
        productName: "유아용 사이즈 딸기 무늬 신발",
        sourceType: "TEXT_IMAGE",
        inputType: "text",
        processingStatus: "COMPLETE",
        resultStatus: "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
        createdAt: new Date("2026-09-02"),
    },
    {
        productId: 3,
        productName: "팔찌 만들기 DIY용 야광 비즈 5색",
        sourceType: "TEXT_IMAGE",
        inputType: "image",
        processingStatus: "COMPLETE",
        resultStatus: "RECHECK_REQUIRED",
        createdAt: new Date("2026-09-03"),
    },
    {
        productId: 4,
        productName: "강아지 겨울용 니트 조끼",
        sourceType: "URL",
        inputType: "url",
        processingStatus: "COMPLETE",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        createdAt: new Date("2026-09-04"),
    },
    {
        productId: 5,
        productName: "실리콘 유아 식판 세트",
        sourceType: "TEXT_IMAGE",
        inputType: "text",
        processingStatus: "COMPLETE",
        resultStatus: "RECHECK_REQUIRED",
        createdAt: new Date("2026-09-05"),
    },
];

function MyPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [page, setPage] = useState(0);

    // TODO: 백엔드 연동 시 걷어내고 필터 / 검색어에 따른 get 요청으로 교체한다.
    // searchTerm과 filter에 변화가 있을 때 작동한다.
    const filteredProducts = useMemo(() => {
        const trimmed = searchTerm.trim();
        return PRODUCTS
            .filter((product) => filter === "all" || product.resultStatus === filter)
            .filter((product) => product.productName.includes(trimmed));
    }, [searchTerm, filter]);

    const totalPages = Math.max(Math.ceil(filteredProducts.length / PAGE_SIZE), 1);
    const pagedProducts = filteredProducts.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

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
