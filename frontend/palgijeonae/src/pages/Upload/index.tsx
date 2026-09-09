import { useState } from "react";

import DefaultBox from "../../components/common/DefaultBox/index.tsx";
import PageIntro from "../../components/common/PageIntro/index.tsx";
import UrlInputForm from "./UrlInputForm.tsx";
import TextImageInputForm from "./TextImageInputForm.tsx";

const INPUT_TYPE_TABS = [
    { key: "url", label: "URL" },
    { key: "text/image", label: "텍스트 / 이미지" },
] as const;

type InputType = typeof INPUT_TYPE_TABS[number]["key"];

function UploadPage() {
    const [inputType, setInputType] = useState<InputType>("url");

    return (
        <div className="flex flex-col gap-8">
            <PageIntro title="상품 업로드" description="상세페이지를 붙여넣거나 이미지·URL로 추가하세요.
여러 상품을 한 번에 담아 한 번의 진단으로 확인할 수 있습니다." />
            <DefaultBox align="left">
                <div className="flex flex-row w-full gap-4">
                    {INPUT_TYPE_TABS.map(({ key, label }) => (
                        <button
                            key={key}
                            type="button"
                            onClick={() => setInputType(key)}
                            className={`flex cursor-pointer items-center justify-center rounded-lg border px-6 py-2 text-base font-medium ${
                                inputType === key ? "border-neutral-border" : "border-transparent"
                            }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>
                {inputType === "url" ? (<UrlInputForm />) : (<TextImageInputForm />)}
            </DefaultBox>
        </div>
    );
}

export default UploadPage;