import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import kakao from "../../assets/login-kakao.png"
import naver from "../../assets/login-naver.png"
import google from "../../assets/login-google.png"

import LoginButton from "./LoginButton.tsx"
import PageIntro from "../../components/common/PageIntro/index.tsx"
import { useAuthStore } from "../../store/useAuthStore.ts"

const API_URL = import.meta.env.VITE_API_URL

function LoginPage() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const navigate = useNavigate()

    // 이미 로그인된 상태에서 뒤로가기 등으로 이 페이지에 들어오면 알리고 메인으로 돌려보낸다.
    useEffect(() => {
        if (isLoggedIn) {
            alert('이미 로그인되어 있습니다.')
            navigate('/', { replace: true })
        }
    }, [isLoggedIn, navigate])

    const handleSocialLogin = (provider: 'kakao' | 'naver' | 'google') => {
        const redirectUri = `${window.location.origin}/oauth/callback`
        window.location.href = `${API_URL}/oauth2/authorization/${provider}?redirect_uri=${encodeURIComponent(redirectUri)}`
    }

    if (isLoggedIn) {
        return null
    }

    return (
        <div className="flex w-lg flex-col rounded-2xl gap-5 px-10 pt-8 pb-12 border border-neutral-border mt-10">
            <PageIntro title="로그인" description="소셜 계정으로 간편하게 로그인 하세요." />
            <LoginButton
                type="카카오"
                image={kakao}
                borderColor="border-[#FBE300]"
                backgroundColor="bg-[#FBE300]"
                textColor="text-[#3B1E1E]"
                onClick={() => handleSocialLogin('kakao')}
            />
            <LoginButton
                type="네이버"
                image={naver}
                borderColor="border-[#1DC800]"
                backgroundColor="bg-[#1DC800]"
                textColor="text-white"
                onClick={() => handleSocialLogin('naver')}
            />
            <LoginButton
                type="구글"
                image={google}
                borderColor="border-[#4285F4]"
                backgroundColor="bg-white"
                textColor="text-[#4285F4]"
                onClick={() => handleSocialLogin('google')}
            />
        </div>
    );
}

export default LoginPage;