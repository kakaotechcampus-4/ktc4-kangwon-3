import { useEffect } from 'react'
import { BrowserRouter, Route,Routes } from 'react-router-dom'

import { reissueAccessToken } from './api/client.ts'
import ProtectedRoute from './components/common/ProtectedRoute/index.tsx'
import Layout from './components/layout/Layout.tsx'
import JudgementPage from './pages/Judgement/index.tsx'
import LoginPage from './pages/Login/index.tsx'
import MainPage from './pages/Main/index.tsx'
import MyPage from './pages/Mypage/index.tsx'
import NotFoundPage from './pages/NotFound/index.tsx'
import OAuthCallbackPage from './pages/OAuthCallback/index.tsx'
import QuestionPage from './pages/Question/index.tsx'
import ResultPage from './pages/Result/index.tsx'
import UploadPage from './pages/Upload/index.tsx'
import { useAuthStore } from './store/useAuthStore.ts'

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
        .catch(() => {})
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
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<MainPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/oauth/callback" element={<OAuthCallbackPage />} />

            <Route element={<ProtectedRoute />}>
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/question" element={<QuestionPage />} />
              <Route path="/judgement" element={<JudgementPage />} />
              <Route path="/result" element={<ResultPage />} />
              <Route path="/mypage" element={<MyPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  )
}

export default App
