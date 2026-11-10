import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/core/client";
import { SourceType } from "@/api/types/common.ts"
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import LoadingSpinner from "@/components/common/LoadingSpinner/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import AddedProductPanel from "@/pages/Upload/components/AddedProductPanel.tsx";
import InputForm from "@/pages/Upload/components/InputForm.tsx";
import InputTypeTabs, { type InputType } from "@/pages/Upload/components/InputTypeTabs.tsx";
import ProductDetailModal from "@/pages/Upload/components/ProductDetailModal.tsx";
import ProductImageLightbox from "@/pages/Upload/components/ProductImageLightbox.tsx";
import UploadActionBar from "@/pages/Upload/components/UploadActionBar.tsx";
import { MAX_PRODUCT_COUNT } from "@/pages/Upload/constants.ts";
import { submitDiagnosis } from "@/pages/Upload/utils/diagnosisPipeline.ts";
import { validateProduct } from "@/pages/Upload/utils/validation.ts";

import type { Product } from "./types.ts";

// 자세히 보기 모달과 이미지 확대 창은 한 번에 하나만 띄운다. view가 무엇을 보여줄지 정하고,
// imageIndex는 확대 창에서 보고 있는(또는 방금 닫은) 상세페이지 이미지 순번이다.
interface DetailState {
    productId: string
    view: "info" | "image"
    imageIndex?: number
}

// 메인 페이지의 평가용 체험 버튼(useDemoStart)이 navigate state로 넘겨주는 샘플 상품.
interface UploadLocationState {
    demoProducts?: Product[]
}

function UploadPage() {
    const [inputType, setInputType] = useState<InputType>(SourceType.Url);
    const location = useLocation();
    const [products, setProducts] = useState<Product[]>(() => (location.state as UploadLocationState | null)?.demoProducts ?? []);
    const [detail, setDetail] = useState<DetailState | null>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();
    const detailProduct = detail ? products.find((product) => product.id === detail.productId) : undefined;

    const handleAddProduct = (product: Product) => {
        setProducts((prev) => [...prev, product]);
    };

    const handleRemoveProduct = (id: string) => {
        setProducts((prev) => prev.filter((product) => product.id !== id));
    };

    const handleRemoveDetailProduct = () => {
        if (detailProduct) {
            handleRemoveProduct(detailProduct.id);
        }
        setDetail(null);
    };

    const handleShowList = () => {
        panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const { mutate: runSubmitDiagnosis, isPending } = useMutation({
        mutationFn: submitDiagnosis,
        onSuccess: (diagnosesId) => {
            navigate(`/judgement/${diagnosesId}`);
        },
        onError: (error) => {
            alert(getErrorMessage(error, "진단 요청에 실패했습니다. 다시 시도해주세요."));
        },
    });

    const handleStartDiagnosis = () => {
        if (products.length === 0) {
            alert("진단할 상품을 먼저 추가해주세요.");
            return;
        }

        const firstInvalidProduct = products.find((product) => validateProduct(product) !== null);
        if (firstInvalidProduct) {
            const error = validateProduct(firstInvalidProduct);
            alert(`${firstInvalidProduct.title || "이름 없는 상품"}: ${error}`);
            return;
        }

        runSubmitDiagnosis(products);
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품 업로드" description="상세페이지 URL을 입력하거나, 상세페이지 본문을 텍스트로 붙여넣어 추가하세요.
최대 10개까지의 상품을 한 번에 담아 한 번의 진단으로 확인할 수 있습니다." />
            {isPending ? (
                <LoadingSpinner label="진단 요청을 보내는 중..." />
            ) : (
                <>
                    {/* xl 이상은 입력 폼 옆에 확인할 제품 패널을 두고, 그보다 좁으면 폼 아래에 한 줄로 쌓는다. */}
                    <div className="flex w-full flex-col gap-6 xl:flex-row xl:items-start">
                        <div className="w-full xl:min-w-0 xl:flex-1">
                            {products.length < MAX_PRODUCT_COUNT ? (
                                <DefaultBox align="left">
                                    <InputTypeTabs selected={inputType} onSelect={setInputType} />
                                    <InputForm key={inputType} type={inputType} onAdd={handleAddProduct} />
                                </DefaultBox>
                            ) : (
                                <DefaultBox tone="warning">
                                    <p className="w-full text-center text-base font-semibold text-status-warning">
                                        상품은 최대 10개까지 담을 수 있어요. 진단을 시작해주세요.
                                    </p>
                                </DefaultBox>
                            )}
                        </div>
                        <div ref={panelRef} className="w-full scroll-mt-20 xl:sticky xl:top-22 xl:w-72 xl:shrink-0">
                            <AddedProductPanel
                                products={products}
                                onOpenDetail={(id) => setDetail({ productId: id, view: "info" })}
                                onRemove={handleRemoveProduct}
                            />
                        </div>
                    </div>
                    <UploadActionBar products={products} onStart={handleStartDiagnosis} onShowList={handleShowList} />
                </>
            )}
            {detailProduct && detail?.view === "info" && (
                <ProductDetailModal
                    product={detailProduct}
                    focusImageIndex={detail.imageIndex}
                    onClose={() => setDetail(null)}
                    onRemove={handleRemoveDetailProduct}
                    onImageClick={(index) => setDetail({ productId: detailProduct.id, view: "image", imageIndex: index })}
                />
            )}
            {detailProduct?.images && detail?.view === "image" && detail.imageIndex !== undefined && (
                <ProductImageLightbox
                    files={detailProduct.images}
                    currentIndex={detail.imageIndex}
                    onIndexChange={(index) => setDetail({ productId: detailProduct.id, view: "image", imageIndex: index })}
                    onClose={() => setDetail({ productId: detailProduct.id, view: "info", imageIndex: detail.imageIndex })}
                />
            )}
        </div>
    );
}

export default UploadPage;
