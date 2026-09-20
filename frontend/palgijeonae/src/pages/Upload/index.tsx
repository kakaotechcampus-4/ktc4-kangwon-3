import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "@/components/common/Button/index.tsx";
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import { cn } from "@/lib/cn";

import AddedProductList from "./AddedProductList.tsx";
import { processProduct } from "./diagnosisPipeline.ts";
import TextImageInputForm from "./TextImageInputForm.tsx";
import type { Product } from "./types.ts";
import UrlInputForm from "./UrlInputForm.tsx";

const INPUT_TYPE_TABS = [
    { key: "url", label: "URL" },
    { key: "text/image", label: "텍스트 / 이미지" },
] as const;

type InputType = typeof INPUT_TYPE_TABS[number]["key"];

function UploadPage() {
    const [inputType, setInputType] = useState<InputType>("url");
    const [products, setProducts] = useState<Product[]>([]);
    const navigate = useNavigate();

    const handleAddProduct = (product: Product) => {
        setProducts((prev) => [...prev, product]);
    };

    const handleRemoveProduct = (id: string) => {
        // thumbnail은 폼에서 URL.createObjectURL로 만들어 문자열로만 들고 있어서,
        // AttachedImageList처럼 자체적으로 revoke되지 않는다. 삭제 시점에 직접 해제한다.
        const target = products.find((product) => product.id === id);
        if (target?.thumbnail) {
            URL.revokeObjectURL(target.thumbnail);
        }

        setProducts((prev) => prev.filter((product) => product.id !== id));
    };

    // TODO: 다중 상품 처리 구현 전까지는 일단 첫 번째 상품만 진단 요청으로 보낸다.
    const { mutate: startDiagnosis } = useMutation({
        mutationFn: () => processProduct(products[0]),
        onSuccess: (diagnosesId) => {
            navigate("/judgement", { state: { diagnosesIds: [diagnosesId] } });
        },
    });

    const handleStartDiagnosis = () => {
        if (products.length === 0) {
            alert("진단할 상품을 먼저 추가해주세요.");
            return;
        }

        startDiagnosis();
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품 업로드" description="상세페이지를 붙여넣거나 이미지·URL로 추가하세요.
여러 상품을 한 번에 담아 한 번의 진단으로 확인할 수 있습니다." />
            <DefaultBox align="left">
                <div className="flex flex-row w-full gap-4">
                    {INPUT_TYPE_TABS.map(({ key, label }) => (
                        <button
                            key={key}
                            type="button"
                            onClick={() => setInputType(key)}
                            className={cn(
                                "flex cursor-pointer items-center justify-center rounded-lg border px-6 py-2 text-base font-medium",
                                inputType === key ? "border-neutral-border" : "border-transparent",
                            )}
                        >
                            {label}
                        </button>
                    ))}
                </div>
                {inputType === "url" ? (
                    <UrlInputForm onAdd={handleAddProduct} />
                ) : (
                    <TextImageInputForm onAdd={handleAddProduct} />
                )}
            </DefaultBox>
            <AddedProductList products={products} onRemove={handleRemoveProduct} />
            <div className="flex w-full justify-end">
                <Button text="진단 시작하기" onClick={handleStartDiagnosis} fontSize={15} />
            </div>
        </div>
    );
}

export default UploadPage;