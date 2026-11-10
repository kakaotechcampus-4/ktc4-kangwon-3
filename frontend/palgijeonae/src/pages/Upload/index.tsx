import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/core/client";
import { SourceType } from "@/api/types/common.ts"
import Button from "@/components/common/Button/index.tsx";
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import LoadingSpinner from "@/components/common/LoadingSpinner/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import AddedProductPanel from "@/pages/Upload/components/AddedProductPanel.tsx";
import InputForm from "@/pages/Upload/components/InputForm.tsx";
import InputTypeTabs, { type InputType } from "@/pages/Upload/components/InputTypeTabs.tsx";
import { submitDiagnosis } from "@/pages/Upload/utils/diagnosisPipeline.ts";
import { validateProduct } from "@/pages/Upload/utils/validation.ts";

import type { Product } from "./types.ts";

// 자세히 보기 모달을 연결하기 전까지는 항목을 눌러도 아무 일도 하지 않는다.
const NOOP = () => {};

// 메인 페이지의 평가용 체험 버튼(useDemoStart)이 navigate state로 넘겨주는 샘플 상품.
interface UploadLocationState {
    demoProducts?: Product[]
}

function UploadPage() {
    const [inputType, setInputType] = useState<InputType>(SourceType.Url);
    const location = useLocation();
    const [products, setProducts] = useState<Product[]>(() => (location.state as UploadLocationState | null)?.demoProducts ?? []);
    const navigate = useNavigate();

    const handleAddProduct = (product: Product) => {
        setProducts((prev) => [...prev, product]);
    };

    const handleRemoveProduct = (id: string) => {
        setProducts((prev) => prev.filter((product) => product.id !== id));
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
                    {products.length < 10 ? (
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
                    <AddedProductPanel products={products} onOpenDetail={NOOP} onRemove={handleRemoveProduct} />
                    <div className="flex w-full justify-end">
                        <Button text="진단 시작하기" onClick={handleStartDiagnosis} fontSize={15} className="w-full md:w-auto" />
                    </div>
                </>
            )}
        </div>
    );
}

export default UploadPage;
