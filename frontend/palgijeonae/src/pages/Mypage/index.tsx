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
            <RevisionNoticeBanner revisedDate="" title="" description="" onCheckClick={() => {}} />
            <DefaultBox>알림 설정</DefaultBox>
            <DefaultBox>검색 / 필터</DefaultBox>
            <MyProductList products={products} />
        </div>
    );
}

export default MyPage;