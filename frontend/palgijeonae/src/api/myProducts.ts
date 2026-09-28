import type { MyProductItem, PageInfo, ResultStatus } from "@/pages/Mypage/types";

interface GetMyProductsParams {
    resultStatus?: ResultStatus;
    keyword?: string;
    page: number;
    size: number;
    sortType: "LATEST" | "OLDEST";
}

interface GetMyProductResult {
    items: MyProductItem[];
    pageInfo: PageInfo;
}

// TODO: 백엔드 연동 전까지 쓰는 임시 목업.
// 실제 연동은 별도 브랜치에서 진행

const PRODUCTS: MyProductItem[] = [
    {
        productId: "1",
        productName: "오이 모양 크런치 말랑이",
        sourceType: "URL",
        processingStatus: "COMPLETED",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        createdAt: new Date("2026-09-01"),
    },
    {
        productId: "2",
        productName: "유아용 사이즈 딸기 무늬 신발",
        sourceType: "TEXT_IMAGE",
        processingStatus: "COMPLETED",
        resultStatus: "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
        createdAt: new Date("2026-09-02"),
    },
    {
        productId: "3",
        productName: "팔찌 만들기 DIY용 야광 비즈 5색",
        sourceType: "TEXT_IMAGE",
        processingStatus: "COMPLETED",
        resultStatus: "RECHECK_REQUIRED",
        createdAt: new Date("2026-09-03"),
    },
    {
        productId: "4",
        productName: "강아지 겨울용 니트 조끼",
        sourceType: "URL",
        processingStatus: "COMPLETED",
        resultStatus: "PURCHASING_AGENT_ALLOWED",
        createdAt: new Date("2026-09-04"),
    },
    {
        productId: "5",
        productName: "실리콘 유아 식판 세트",
        sourceType: "TEXT_IMAGE",
        processingStatus: "COMPLETED",
        resultStatus: "RECHECK_REQUIRED",
        createdAt: new Date("2026-09-05"),
    },
    {
        productId: "6",
        productName: "차량용 접이식 트렁크 정리함",
        sourceType: "URL",
        processingStatus: "PENDING",
        createdAt: new Date("2026-09-06"),
    },
    {
        productId: "7",
        productName: "휴대용 미니 가습기",
        sourceType: "TEXT_IMAGE",
        processingStatus: "IN_PROGRESS",
        createdAt: new Date("2026-09-07"),
    },
    {
        productId: "8",
        productName: "아기 이유식 실리콘 트레이",
        sourceType: "TEXT_IMAGE",
        processingStatus: "AWAITING_INPUT",
        createdAt: new Date("2026-09-08"),
    },
    {
        productId: "9",
        productName: "무선 이어폰 방수 케이스",
        sourceType: "URL",
        processingStatus: "FAILED",
        createdAt: new Date("2026-09-09"),
    },
];

// TODO: 백엔드 연동 시 이 함수의 내부만 백엔드 api GET 호출로 교체한다.
export async function getMyProducts(params: GetMyProductsParams): Promise<GetMyProductResult> {
    const filtered = PRODUCTS
        .filter((p) => !params.resultStatus || p.resultStatus === params.resultStatus)
        .filter((p) => !params.keyword || p.productName.includes(params.keyword));
    const totalPages = Math.max(Math.ceil(filtered.length / params.size), 1);
    return {
        items: filtered.slice(params.page * params.size, (params.page + 1) * params.size),
        pageInfo: {
            page: params.page,
            size: params.size,
            totalElements: filtered.length,
            totalPages,
            hasNext: params.page < totalPages - 1,
        },
    };
}