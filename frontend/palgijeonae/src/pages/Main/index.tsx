import { useNavigate } from "react-router-dom"

import { useAuthStore } from "../../store/useAuthStore.ts"

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
        <div>
            <div>
                <img src={QuestionMarkIcon} alt="Question Mark" />
                <h1>이 물건, 팔아도 되나요?</h1>
            </div>
            <div>
                <p>구매대행·사입으로 판매할 상품이 국내 법령에 걸리는지,</p>
                <p>AI 에이전트 전문가가 관련 법령과 규제를 실제로 짚어서 확인합니다.</p>
            </div>
            <div>
                <InformationCard image={images} title="여러 상품 한 번에" description="상세페이지 텍스트·이미지·URL, 무엇으로 담든 한 번의 진단으로 확인합니다." />
                <InformationCard image={document} title="근거까지 남기는 문서" description="진단서·소명서·공급사 문의 초안까지 필요할 때 바로 만들어 씁니다."/>
                <InformationCard image={bell} title="기록과 변경 알림" description="확인한 상품은 마이페이지에 남고, 관련 고시가 바뀌면 알려드립니다."/>
            </div>
            <Button text={isLoggedIn ? "진단 시작하기" : "로그인 후 진단 시작"} onClick={handleButtonClick}/>
        </div>
    );
}

export default MainPage;