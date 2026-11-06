import AgentIntro from "./AgentIntro"
import HowToUse from "./HowToUse"
import Intro from "./Intro"
import Preview from "./Preview"

/** 메인 페이지. 소개·서비스 미리보기·사용 방법·에이전트 소개 섹션을 순서대로 배치한다. */
function MainPage() {
    return (
        <div className="flex w-full flex-col items-start gap-20">
            <Intro />
            <Preview />
            <HowToUse />
            <AgentIntro />
            <p className="text-base leading-4.5 text-neutral-text">국가법령정보센터·관세청 등이 공개한 법령과 고시를 기준으로 확인합니다.</p>
        </div>
    );
}

export default MainPage;
