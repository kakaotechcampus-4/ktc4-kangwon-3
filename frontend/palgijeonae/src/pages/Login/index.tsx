import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import google from "@/assets/login-google.png"
import kakao from "@/assets/login-kakao.png"
import naver from "@/assets/login-naver.png"
import SectionIntro from "@/components/common/SectionIntro/index.tsx"
import { useAuthStore } from "@/store/useAuthStore.ts"

import LoginButton from "./LoginButton.tsx"

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
                provider="kakao"
                label="카카오"
                image={kakao}
                onClick={() => handleSocialLogin('kakao')}
            />
            <LoginButton
                provider="naver"
                label="네이버"
                image={naver}
                onClick={() => handleSocialLogin('naver')}
            />
            <LoginButton
                provider="google"
                label="구글"
                image={google}
                onClick={() => handleSocialLogin('google')}
            />
        </div>
    );
}

export default LoginPage;