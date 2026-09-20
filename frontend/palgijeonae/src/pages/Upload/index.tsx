import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "@/components/common/Button/index.tsx";
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import { cn } from "@/lib/cn";

import AddedProductList from "./AddedProductList.tsx";
import { processProduct } from "./diagnosisPipeline.ts";
import TextImageInputForm from "./TextImageInputForm.tsx";
import type { DiagnosisStatus, Product } from "./types.ts";
import UrlInputForm from "./UrlInputForm.tsx";

const INPUT_TYPE_TABS = [
    { key: "url", label: "URL" },
    { key: "text/image", label: "텍스트 / 이미지" },
] as const;

type InputType = typeof INPUT_TYPE_TABS[number]["key"];

function UploadPage() {
    const [inputType, setInputType] = useState<InputType>("url");
    const [products, setProducts] = useState<Product[]>([]);
    // 상품별 진단 요청 진행 상태(pending/failed만 의미 있음). 성공한 상품은 목록에서 바로 빼내고
    // id는 diagnosesIds에 누적하므로, 여기 남아있는 건 항상 "아직 안 끝난" 상품뿐이다.
    const [diagnosisStatuses, setDiagnosisStatuses] = useState<Record<string, DiagnosisStatus>>({});
    const [succeededDiagnosesIds, setSucceededDiagnosesIds] = useState<number[]>([]);
    // 제출 이후엔 입력 폼을 숨겨서, 재시도 대상과 신규 상품이 섞여 들어가지 않게 한다.
    const [hasSubmitted, setHasSubmitted] = useState(false);
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
        setDiagnosisStatuses((prev) => {
            const { [id]: _removed, ...rest } = prev;
            return rest;
        });
    };

    const { mutateAsync: runDiagnosis } = useMutation({ mutationFn: processProduct });

    // 상품 하나를 진단 요청으로 보낸다(최초 제출과 재시도가 공유). 여러 상품을 동시에 보낼 때
    // mutate의 콜백은 호출별로 보장되지 않아, mutateAsync로 호출마다 독립된 Promise를 받는다.
    const submitProduct = (product: Product) => {
        if (diagnosisStatuses[product.id]?.state === "pending") {
            return;
        }

        setDiagnosisStatuses((prev) => ({ ...prev, [product.id]: { state: "pending" } }));
        runDiagnosis(product)
            .then((diagnosesId) => {
                setSucceededDiagnosesIds((prev) => [...prev, diagnosesId]);
                setProducts((prev) => prev.filter((p) => p.id !== product.id));
                setDiagnosisStatuses((prev) => {
                    const { [product.id]: _removed, ...rest } = prev;
                    return rest;
                });
            })
            .catch(() => {
                setDiagnosisStatuses((prev) => ({ ...prev, [product.id]: { state: "failed" } }));
            });
    };

    const hasFailedProduct = products.some((product) => diagnosisStatuses[product.id]?.state === "failed");

    const handleStartDiagnosis = () => {
        if (products.length === 0) {
            alert("진단할 상품을 먼저 추가해주세요.");
            return;
        }

        setHasSubmitted(true);
        // 성공한 상품은 이미 목록에서 빠져있어서, 여기 남은 건 항상 신규 or 재시도 대상뿐이다.
        products.forEach(submitProduct);
    };

    // 목록에 남은 상품이 하나도 없을 때(=전부 성공)만, 그동안 쌓인 id로 한 번에 판정 페이지로 넘어간다.
    useEffect(() => {
        if (succeededDiagnosesIds.length === 0 || products.length > 0) {
            return;
        }

        navigate("/judgement", { state: { diagnosesIds: succeededDiagnosesIds } });
    }, [products, succeededDiagnosesIds, navigate]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품 업로드" description="상세페이지를 붙여넣거나 이미지·URL로 추가하세요.
여러 상품을 한 번에 담아 한 번의 진단으로 확인할 수 있습니다." />
            {!hasSubmitted && (
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
            )}
            <AddedProductList products={products} statuses={diagnosisStatuses} onRemove={handleRemoveProduct} />
            <div className="flex w-full justify-end">
                <Button text={hasFailedProduct ? "재시도" : "진단 시작하기"} onClick={handleStartDiagnosis} fontSize={15} />
            </div>
        </div>
    );
}

export default UploadPage;
