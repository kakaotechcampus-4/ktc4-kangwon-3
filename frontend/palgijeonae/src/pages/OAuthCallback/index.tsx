import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'

import { useAuthStore } from '../../store/useAuthStore'

const API_URL = import.meta.env.VITE_API_URL

function OAuthCallbackPage() {
    const [searchParams] = useSearchParams()
    const navigate = useNavigate()
    const login = useAuthStore((state) => state.login)
    // reissue는 refresh token을 회전시키는 1회성 작업이라 StrictMode의 effect 이중 실행에도 한 번만 돌아야 함
    const hasRun = useRef(false)

    useEffect(() => {
        if (hasRun.current) return
        hasRun.current = true

        // 소셜 로그인 실패 시 BE가 ?error={code}를 붙여 이 페이지로 리다이렉트함
        if (searchParams.get('error')) {
            navigate('/login', { replace: true })
            return
        }

        // isNewUser는 온보딩 분기용 신호(문서 참고)인데, 아직 온보딩 플로우가 없어 사용하지 않음

        const reissue = async () => {
            try {
                // refresh_token은 HttpOnly 쿠키로만 전달되므로 withCredentials 필수
                const response = await axios.post(
                    `${API_URL}/api/v1/auth/reissue`,
                    null,
                    { withCredentials: true }
                )

                login(response.data.data.accessToken)
                alert('로그인 되었습니다.')
                navigate('/', { replace: true })
            } catch {
                // 쿠키 없음/만료/폐기(AUTH-003) 등 — 재로그인 유도
                navigate('/login', { replace: true })
            }
        }

        reissue()
    }, [searchParams, navigate, login])

    return (
        <div className="flex w-full items-center justify-center py-20">
            <p className="text-lg text-neutral-text">로그인 처리 중입니다...</p>
        </div>
    );
}

export default OAuthCallbackPage;
