import SectionIntro from "@/components/common/SectionIntro";

import { HOW_TO_USE_STEPS } from "./constants";
import HowToUseStep from "./HowToUseStep";

/** 메인 페이지 "사용 방법" 섹션. 상품 담기부터 결과 확인까지 4단계를 타임라인으로 보여준다. */
function HowToUse() {
    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="이렇게 진행돼요" description="상품을 담으면 결과까지 아래 순서로 이어져요." size="2xl" />
            <ol className="flex flex-col pl-15">
                {HOW_TO_USE_STEPS.map((step, index) => (
                    <HowToUseStep
                        key={step.key}
                        stepNumber={index + 1}
                        isLast={index === HOW_TO_USE_STEPS.length - 1}
                        title={step.title}
                        tag={step.tag}
                        description={step.description}
                        tips={step.tips}
                        preview={<step.Preview />}
                    />
                ))}
            </ol>
        </div>
    );
}

export default HowToUse;
