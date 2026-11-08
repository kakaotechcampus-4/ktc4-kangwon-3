import { type LawAmendment } from "@/api/lawAmendments";
import { isLawAmendmentAlertEnabled } from "@/api/mock/users";
import { ToolName } from "@/api/types/product";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/lawAmendments" 대신 "@/api/mock/lawAmendments"로 바꾸면 된다.
 */

let mockLawAmendments: LawAmendment[] = [
    {
        lawAmendmentId: "law-amendment-1",
        lawName: "전기용품 및 생활용품 안전관리법 시행규칙",
        revisionType: "일부개정",
        toolName: ToolName.Electrical,
        enforceDate: "2026-12-01",
        products: [
            { productId: "product-1", productName: "무선 블루투스 이어폰 노이즈캔슬링 프리미엄 에디션 화이트" },
            { productId: "product-2", productName: "휴대용 선풍기" },
        ],
    },
    {
        lawAmendmentId: "law-amendment-2",
        lawName: "어린이제품 안전 특별법 시행령",
        revisionType: null,
        toolName: ToolName.Children,
        enforceDate: null,
        products: [{ productId: "product-3", productName: "유아용 장난감 세트" }],
    },
];

/** 개발용 법령 개정 알림 조회 함수. 알림을 끄면 빈 목록을 돌려준다. */
export async function getLawAmendments(): Promise<LawAmendment[]> {
    return isLawAmendmentAlertEnabled() ? mockLawAmendments : [];
}

/** 재진단하거나 삭제한 상품을 목업 개정 목록에서 뺀다. 상품이 하나도 안 남은 개정도 함께 뺀다. */
export function removeProductFromLawAmendments(productId: string) {
    mockLawAmendments = mockLawAmendments
        .map((amendment) => ({ ...amendment, products: amendment.products.filter((product) => product.productId !== productId) }))
        .filter((amendment) => amendment.products.length > 0);
}
