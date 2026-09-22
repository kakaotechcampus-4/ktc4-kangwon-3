import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";

import MyProductList from "./MyProductList.tsx";
import RevisionNoticeBanner from "./RevisionNoticeBanner.tsx";
import type { MyProductItem } from "./types.ts";

function MyPage() {
    const products: MyProductItem[] = [];

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="마이페이지" description="지금까지 진단한 상품들을 확인할 수 있어요" />
            <RevisionNoticeBanner revisedDate="2026-09-03" title="어린이제품 안전 특별법 시행규칙 별표2가 개정되었습니다. 완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다." description="사입으로 등록한 상품 1개는 재확인이 필요합니다. 구매대행 상품은 이 조문의 적용을 받지 않아 영향이 없습니다." onCheckClick={() => {}} />
            <DefaultBox>알림 설정</DefaultBox>
            <DefaultBox>검색 / 필터</DefaultBox>
            <MyProductList products={products} />
        </div>
    );
}

export default MyPage;