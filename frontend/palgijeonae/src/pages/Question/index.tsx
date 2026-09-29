import { useState } from "react";

import SectionIntro from "@/components/common/SectionIntro";
import ProductTabs from "@/components/common/ProductTabs";
import DefaultBox from "@/components/common/DefaultBox";

function QuestionPage() {
    // TODO: api 연동 기반을 마련하고 삭제할 목업 데이터
    const productNames = ["제품 1", "제품 2", "제품 3"]
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);

    return ( 
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단에 필요한 질문이 몇 가지 있어요" description="추가적인 확인이 필요한 정보들을 확인합니다. 제품 각각 입력해주세요."/>
            <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
            <div className="flex flex-col gap-4">
                질문 리스트
            </div>
        </div>
     );
}

export default QuestionPage;