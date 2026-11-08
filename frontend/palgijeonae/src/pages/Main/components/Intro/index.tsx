import { useNavigate } from "react-router-dom"

import Favicon from "@/assets/favicon.svg"
import Button from "@/components/common/Button"
import DemoButton from "@/pages/Main/components/Intro/components/DemoButton"
import { useAuthStore } from "@/store/useAuthStore.ts"

/** 메인 페이지 최상단 소개 영역. 서비스 제목·설명과 로그인 상태에 따른 시작 버튼, 예시 체험 버튼을 보여준다. */
function Intro() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isAuthReady = useAuthStore((state) => state.isAuthReady)
    const navigate = useNavigate()

    const handleButtonClick = () => {
        if (isLoggedIn) {
            navigate("/upload");
        } else {
            navigate("/login");
        }
    }

    return (
        <div className="flex w-full flex-col items-start gap-6">
            <div className="flex w-full flex-row items-center gap-2 py-1">
                <img src={Favicon} alt="" className="size-10 shrink-0 object-contain md:size-13" />
                <h1 className="text-[22px] font-extrabold leading-8 text-black md:text-4xl md:leading-10">이 물건, 팔아도 되나요?</h1>
            </div>
            <p className="text-base leading-5.5 text-neutral-text md:text-lg md:leading-8.5">
                구매대행·사입으로 판매할 상품이 국내 법령에 걸리는지,{" "}
                <br className="hidden md:block" />
                AI 에이전트가 관련 법령과 규제를 실제로 짚어서 확인해요.
            </p>
            {isAuthReady && (
                <div className="grid w-full grid-cols-2 items-start gap-2 [&>*:only-child]:col-span-2 md:flex md:flex-wrap md:items-center md:gap-2.5">
                    <Button text={isLoggedIn ? "상품 확인 시작하기" : "로그인 후 진단 시작"} onClick={handleButtonClick} fontSize={15} className="w-full px-3 md:w-auto md:px-6.25" />
                    <DemoButton />
                </div>
            )}
        </div>
    );
}

export default Intro;
