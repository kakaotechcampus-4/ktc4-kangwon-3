import * as Sentry from '@sentry/react'
import { useEffect } from 'react'
import { BrowserRouter, Route,Routes } from 'react-router-dom'

import { reissueAccessToken } from '@/api/core/client.ts'
import { isSessionRejectedError } from '@/api/core/sessionRejected.ts'
import { clearAllAnswerDrafts } from '@/pages/Question/utils/answerDraft.ts'

import ProtectedRoute from './components/common/ProtectedRoute/index.tsx'
import Layout from './components/layout/Layout.tsx'
import JudgementPage from './pages/Judgement/index.tsx'
import LoginPage from './pages/Login/index.tsx'
import MainPage from './pages/Main/index.tsx'
import MyPage from './pages/Mypage/index.tsx'
import NotFoundPage from './pages/NotFound/index.tsx'
import OAuthCallbackPage from './pages/OAuthCallback/index.tsx'
import PolicyPage from './pages/Policy/index.tsx'
import QuestionPage from './pages/Question/index.tsx'
import ResultPage from './pages/Result/index.tsx'
import UploadPage from './pages/Upload/index.tsx'
import { useAuthStore } from './store/useAuthStore.ts'

// Routes 교체는 앱 최상단에서 한 번만 한다.
const SentryRoutes = Sentry.wrapReactRouterRouting(Routes)

function App() {
  useEffect(() => {
    // accessToken은 메모리에만 있어 새로고침으로 사라지므로, refresh_token 쿠키로 세션을 복구한다.
    // /oauth/callback은 자체적으로 reissue를 수행하므로 여기서는 건너뛴다.
    const restoreSession = () => {
      if (window.location.pathname === '/oauth/callback') {
        return
      }
      // bfcache로 복원된 페이지는 zustand 상태도 그대로 유지되므로,
      // 이미 로그인 상태라면 reissue로 리프레시 토큰을 불필요하게 회전시키지 않는다.
      if (useAuthStore.getState().isLoggedIn) {
        useAuthStore.getState().markAuthReady()
        return
      }
      reissueAccessToken()
        .catch((error) => {
          // 앱을 새로 열 때 서버가 세션을 거절하면 logout()을 거치지 않으므로, 이전 회원의 임시 답변을 여기서 지운다.
          // 네트워크 오류처럼 잠시 실패한 경우에는 작성 중인 답변을 지키려고 남긴다.
          if (isSessionRejectedError(error)) {
            clearAllAnswerDrafts()
          }
        })
        .finally(() => useAuthStore.getState().markAuthReady())
    }

    restoreSession()

    // 뒤로/앞으로가기는 리로드 없이 bfcache로 복원되어 위 로직이 재실행되지 않으므로, pageshow로 감지한다.
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        restoreSession()
      }
    }
    window.addEventListener('pageshow', handlePageShow)
    return () => window.removeEventListener('pageshow', handlePageShow)
  }, [])

  return (
    <div className="">
      <BrowserRouter>
        <SentryRoutes>
          <Route element={<Layout />}>
            <Route path="/" element={<MainPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
            <Route path="/policy/:type" element={<PolicyPage />} />

            <Route element={<ProtectedRoute />}>
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/question" element={<QuestionPage />} />
              <Route path="/question/:productId" element={<QuestionPage />} />
              <Route path="/judgement" element={<JudgementPage />} />
              <Route path="/judgement/:diagnosesId" element={<JudgementPage />} />
              <Route path="/result/product/:productId" element={<ResultPage />} />
              <Route path="/result/diagnoses/:diagnosesId" element={<ResultPage />} />
              <Route path="/mypage" element={<MyPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </SentryRoutes>
      </BrowserRouter>
    </div>
  )
}

export default App
