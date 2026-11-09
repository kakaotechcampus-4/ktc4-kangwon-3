import AgentIntro from "@/pages/Main/components/AgentIntro"
import HowToUse from "@/pages/Main/components/HowToUse"
import Intro from "@/pages/Main/components/Intro"
import Preview from "@/pages/Main/components/Preview"

/** 메인 페이지. 소개·서비스 미리보기·사용 방법·에이전트 소개 섹션을 순서대로 배치한다. */
function MainPage() {
    return (
        <div className="flex w-full flex-col items-start gap-14 md:gap-20">
            <Intro />
            <Preview />
            <HowToUse />
            <AgentIntro />
        </div>
    );
}

export default MainPage;
