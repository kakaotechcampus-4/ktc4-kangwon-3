import ProductPreview from "@/components/common/ProductPreview";
import SectionIntro from "@/components/common/SectionIntro";
import { NOOP, PREVIEW_PRODUCTS, REVISION_NOTICE } from "@/pages/Main/previewMocks";
import RevisionNoticeBanner from "@/pages/Mypage/RevisionNoticeBanner";

// 진단 결과 상태가 서로 다른 예시 3개를 보여준다.
const EXAMPLE_PRODUCTS = [PREVIEW_PRODUCTS.earphoneResult, PREVIEW_PRODUCTS.table, PREVIEW_PRODUCTS.slipperResult];

/** 메인 페이지 "마이페이지 안내" 섹션. 진단 기록 다시 보기 / 고시 개정 알림을 실제 컴포넌트로 보여준다. */
function MyPageIntro() {
    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro
                title="마이페이지에서 한눈에 확인해요"
                description="지금까지 진단한 상품을 모아보고, 관련 고시가 바뀌면 알려드려요."
                size="2xl"
            />
            <div className="@container flex w-full flex-col gap-10">
                <div className="flex flex-col gap-4">
                    <SectionIntro title="진단 기록 다시 보기" size="xl" />
                    <div className="flex flex-col gap-3.5">
                        {EXAMPLE_PRODUCTS.map((product) => (
                            <ProductPreview
                                key={product.productId}
                                productName={product.productName}
                                productImageUrl={product.productImageUrl}
                                resultStatus={product.resultStatus}
                                processingStatus={product.processingStatus}
                                sourceType={product.sourceType}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default MyPageIntro;
