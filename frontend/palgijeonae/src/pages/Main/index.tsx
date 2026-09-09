import { useNavigate } from "react-router-dom"

import Button from "../../components/common/Button"
import InformationCard from "./InformationCard.tsx"

import QuestionMarkIcon from "../../assets/main-questionMark.png"
import images from "../../assets/main-images.png"
import document from "../../assets/main-document.png"
import bell from "../../assets/main-bell.png"

function MainPage() {
    // const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
    const isLoggedIn = true
    const navigate = useNavigate()

    const handleButtonClick = () => {
        if (isLoggedIn) {
            navigate("/upload");
        } else {
            navigate("/login");
        }
    }

    return (
        <div className="flex w-full min-w-150 flex-col items-start gap-6">
            <div className="flex w-full flex-row items-center gap-2 py-1">
                <img src={QuestionMarkIcon} alt="Question Mark" className="h-17 w-17 shrink-0 object-contain" />
                <h1 className="text-4xl font-extrabold leading-10 text-black">이 물건, 팔아도 되나요?</h1>
            </div>
            <div className="flex w-full flex-col items-start gap-0.5">
                <p className="text-lg leading-5.5 text-neutral-text">구매대행·사입으로 판매할 상품이 국내 법령에 걸리는지,</p>
                <p className="text-lg leading-5.5 text-neutral-text">AI 에이전트 전문가가 관련 법령과 규제를 실제로 짚어서 확인합니다.</p>
            </div>
            <div className="flex w-full h-auto flex-row justify-center gap-8">
                <InformationCard image={images} title="여러 상품 한 번에" description="상세페이지 텍스트·이미지·URL, 무엇으로 담든 한 번의 진단으로 확인합니다." />
                <InformationCard image={document} title="근거까지 남기는 문서" description="진단서·소명서·공급사 문의 초안까지 필요할 때 바로 만들어 씁니다."/>
                <InformationCard image={bell} title="기록과 변경 알림" description="확인한 상품은 마이페이지에 남고, 관련 고시가 바뀌면 알려드립니다."/>
            </div>
            <div className="flex w-full flex-col items-start gap-6.25">
                <Button text={isLoggedIn ? "상품 확인 시작하기" : "로그인 후 진단 시작"} onClick={handleButtonClick} fontSize={18} />
                <p className="text-base leading-4.5 text-neutral-text">국가법령정보센터·관세청 등이 공개한 법령과 고시를 기준으로 확인합니다.</p>
            </div>
        </div>
    );
}

export default MainPage;