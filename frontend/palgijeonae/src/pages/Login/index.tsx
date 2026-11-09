import { useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"

import google from "@/assets/login-google.png"
import kakao from "@/assets/login-kakao.png"
// TODO: Naver 로그인 기능은 공개 심사 준비 이슈로 화면에 표시하지 않음.
// import naver from "@/assets/login-naver.png"
import SectionIntro from "@/components/common/SectionIntro/index.tsx"
import { POLICY_LINKS } from "@/constants/navigation.ts"
import LoginButton from "@/pages/Login/components/LoginButton.tsx"
import { useAuthStore } from "@/store/useAuthStore.ts"

import { Provider } from "./types.ts"

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

    const handleSocialLogin = (provider: Provider) => {
        const redirectUri = `${window.location.origin}/oauth/callback`
        window.location.href = `${API_URL}/oauth2/authorization/${provider}?redirect_uri=${encodeURIComponent(redirectUri)}`
    }

    if (isLoggedIn) {
        return null
    }

    return (
        <div className="flex w-full flex-col rounded-2xl gap-5 px-6 pt-8 pb-10 border border-box-line bg-white shadow-box mt-2 md:w-lg md:px-10 md:pb-12 md:mt-10">
            <SectionIntro title="로그인" description="소셜 계정으로 간편하게 로그인 하세요." />
            <LoginButton
                provider={Provider.Kakao}
                label="카카오"
                image={kakao}
                onClick={() => handleSocialLogin(Provider.Kakao)}
            />
            {/* TODO: Naver 로그인 기능은 공개 심사 준비 이슈로 화면에 표시하지 않음. */}
            {/* <LoginButton
                provider={Provider.Naver}
                label="네이버"
                image={naver}
                onClick={() => handleSocialLogin(Provider.Naver)}
            /> */}
            <LoginButton
                provider={Provider.Google}
                label="구글"
                image={google}
                onClick={() => handleSocialLogin(Provider.Google)}
            />
            <p className="w-full text-center text-xs leading-5 text-neutral-label md:text-[13px]">
                로그인 시{" "}
                <Link to={POLICY_LINKS.terms.to} className="font-medium text-neutral-text underline">
                    {POLICY_LINKS.terms.label}
                </Link>
                과{" "}
                <Link to={POLICY_LINKS.privacy.to} className="font-medium text-neutral-text underline">
                    {POLICY_LINKS.privacy.label}
                </Link>
                에 동의하는 것으로 간주합니다.
            </p>
        </div>
    );
}

export default LoginPage;