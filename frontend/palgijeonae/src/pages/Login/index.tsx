import kakao from "../../assets/login-kakao.png"
import naver from "../../assets/login-naver.png"
import google from "../../assets/login-google.png"

import LoginButton from "./LoginButton.tsx"

function LoginPage() {
    return (
        <div className="flex w-lg flex-col rounded-2xl gap-5 px-10 py-12 border border-neutral-border mt-10">
            <LoginButton
                type="카카오"
                image={kakao}
                BorderColor="border-[#FBE300]"
                BackgroundColor="bg-[#FBE300]"
                textColor="text-[#3B1E1E]"
                onClick={() => {
                    // 카카오 로그인 로직
                }}
            />
            <LoginButton
                type="네이버"
                image={naver}
                BorderColor="border-[#1DC800]"
                BackgroundColor="bg-[#1DC800]"
                textColor="text-white"
                onClick={() => {
                    // 네이버 로그인 로직
                }}
            />
            <LoginButton
                type="구글"
                image={google}
                BorderColor="border-[#4285F4]"
                BackgroundColor="bg-white"
                textColor="text-[#4285F4]"
                onClick={() => {
                    // 구글 로그인 로직
                }}
            />
        </div>
    );
}

export default LoginPage;