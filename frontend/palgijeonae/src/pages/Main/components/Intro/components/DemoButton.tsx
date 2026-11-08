import Button from "@/components/common/Button";
import HelpTooltip from "@/components/common/HelpTooltip";
import { useDemoStart } from "@/pages/Main/components/Intro/hooks/useDemoStart";

// 평가 모드가 true 일때만 DemoButton을 노출한다. false이면 null을 반환한다.
const IS_DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

/** 평가용으로만 노출되는 체험 버튼. 샘플 상품이 이미 담긴 업로드 페이지로 바로 이동한다. */
function DemoButton() {
    const startDemo = useDemoStart();

    if (!IS_DEMO_MODE) {
        return null;
    }

    return (
        <div className="flex w-full items-center gap-3 md:w-auto">
            <Button text="예시 상품으로 체험하기" onClick={startDemo} fontSize={15} variant="secondary" className="flex-1 md:flex-none" />
            <HelpTooltip label="예시 상품 체험 설명">
                미리 준비된 상품이 담긴 업로드 페이지로 이동해요.{"\n"}
                이동한 업로드 페이지에서 "진단 시작하기" 버튼을 누르면 실제 에이전트가 진단을 시작해요.
            </HelpTooltip>
        </div>
    );
}

export default DemoButton;
