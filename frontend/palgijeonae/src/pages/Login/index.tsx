import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import kakao from "@/assets/login-kakao.png"
import naver from "@/assets/login-naver.png"
import google from "@/assets/login-google.png"

import LoginButton from "./LoginButton.tsx"
import SectionIntro from "@/components/common/SectionIntro/index.tsx"
import { useAuthStore } from "@/store/useAuthStore.ts"

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
            <SectionIntro title="로그인" description="소셜 계정으로 간편하게 로그인 하세요." />
            <LoginButton
                type="카카오"
                image={kakao}
                borderColor="border-[#FEE500]"
                backgroundColor="bg-[#FEE500]"
                textColor="text-black/85"
                onClick={() => handleSocialLogin('kakao')}
            />
            <LoginButton
                type="네이버"
                image={naver}
                borderColor="border-[#03A94D]"
                backgroundColor="bg-[#03A94D]"
                textColor="text-white"
                onClick={() => handleSocialLogin('naver')}
            />
            <LoginButton
                type="구글"
                image={google}
                borderColor="border-[#747775]"
                backgroundColor="bg-white"
                textColor="text-[#1F1F1F]"
                onClick={() => handleSocialLogin('google')}
            />
        </div>
    );
}

export default LoginPage;