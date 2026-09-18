import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { reissueAccessToken } from '@/api/client'

function OAuthCallbackPage() {
    const [searchParams] = useSearchParams()
    const navigate = useNavigate()
    // reissue는 refresh token을 회전시키는 1회성 작업이라 StrictMode의 effect 이중 실행에도 한 번만 돌아야 함
    const hasRun = useRef(false)

    const reissueMutation = useMutation({
        // client.ts의 axios 인터셉터와 동일한 요청/로그인 처리를 재사용 (중복 호출 방지용 refreshPromise 캐싱도 그대로 적용됨)
        mutationFn: reissueAccessToken,
        onSuccess: () => {
            navigate('/', { replace: true })
        },
        onError: () => {
            // 쿠키 없음/만료/폐기(AUTH-003) 등 — 재로그인 유도
            navigate('/login', { replace: true })
        },
    })

    useEffect(() => {
        if (hasRun.current) return
        hasRun.current = true

        // 소셜 로그인 실패 시 BE가 ?error={code}를 붙여 이 페이지로 리다이렉트함
        if (searchParams.get('error')) {
            navigate('/login', { replace: true })
            return
        }

        // isNewUser는 온보딩 분기용 신호(문서 참고)인데, 아직 온보딩 플로우가 없어 사용하지 않음

        reissueMutation.mutate()
        // reissueMutation.mutate는 재렌더와 무관하게 안정적인 참조라 의존성에서 제외
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams, navigate])

    return (
        <div className="flex w-full flex-col items-center justify-center gap-4 py-20">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-neutral-border border-t-primary" />
            <p className="text-lg text-neutral-text">로그인 처리 중입니다...</p>
        </div>
    );
}

export default OAuthCallbackPage;
