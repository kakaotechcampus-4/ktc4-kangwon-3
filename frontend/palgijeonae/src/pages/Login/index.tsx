import kakao from "../../assets/login-kakao.png"
import naver from "../../assets/login-naver.png"
import google from "../../assets/login-google.png"

import LoginButton from "./LoginButton.tsx"
import PageIntro from "../../components/common/PageIntro/index.tsx"

const API_URL = import.meta.env.VITE_API_URL

function LoginPage() {
    const handleSocialLogin = (provider: 'kakao' | 'naver' | 'google') => {
        window.location.href = `${API_URL}/oauth2/authorization/${provider}`
    }

    return (
        <div className="flex w-lg flex-col rounded-2xl gap-5 px-10 pt-8 pb-12 border border-neutral-border mt-10">
            <PageIntro title="로그인" description="소셜 계정으로 간편하게 로그인 하세요." />
            <LoginButton
                type="카카오"
                image={kakao}
                BorderColor="border-[#FBE300]"
                BackgroundColor="bg-[#FBE300]"
                textColor="text-[#3B1E1E]"
                onClick={() => handleSocialLogin('kakao')}
            />
            <LoginButton
                type="네이버"
                image={naver}
                BorderColor="border-[#1DC800]"
                BackgroundColor="bg-[#1DC800]"
                textColor="text-white"
                onClick={() => handleSocialLogin('naver')}
            />
            <LoginButton
                type="구글"
                image={google}
                BorderColor="border-[#4285F4]"
                BackgroundColor="bg-white"
                textColor="text-[#4285F4]"
                onClick={() => handleSocialLogin('google')}
            />
        </div>
    );
}

export default LoginPage;