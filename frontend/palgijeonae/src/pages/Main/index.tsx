import Intro from "./Intro"
import Preview from "./Preview"

function MainPage() {
    return (
        <div className="flex w-full flex-col items-start gap-6">
            <Intro />
            <div className="mt-14 w-full">
                <Preview />
            </div>
            <p className="text-base leading-4.5 text-neutral-text">국가법령정보센터·관세청 등이 공개한 법령과 고시를 기준으로 확인합니다.</p>
        </div>
    );
}

export default MainPage;
