import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

import { reissueAccessToken } from './api/client.ts'
import { useAuthStore } from './store/useAuthStore.ts'
import Layout from './components/layout/Layout.tsx'
import ProtectedRoute from './components/common/ProtectedRoute/index.tsx'
import MainPage from './pages/Main/index.tsx'
import LoginPage from './pages/Login/index.tsx'
import OAuthCallbackPage from './pages/OAuthCallback/index.tsx'
import UploadPage from './pages/Upload/index.tsx'
import QuestionPage from './pages/Question/index.tsx'
import JudgementPage from './pages/Judgement/index.tsx'
import ResultPage from './pages/Result/index.tsx'
import MyPage from './pages/Mypage/index.tsx'
import NotFoundPage from './pages/NotFound/index.tsx'

function App() {
  useEffect(() => {
    // 새로고침 등으로 앱이 새로 로드되면 accessToken은 메모리에서 사라지므로,
    // refresh_token 쿠키가 남아있다면 여기서 한 번 재발급받아 로그인 상태를 복구한다.
    // /oauth/callback은 자체적으로 reissue를 수행하므로 중복 호출을 피한다.
    const restoreSession = () => {
      if (window.location.pathname === '/oauth/callback') {
        return
      }
      reissueAccessToken()
        .catch(() => {})
        .finally(() => useAuthStore.getState().markAuthReady())
    }

    restoreSession()

    // 뒤로/앞으로가기는 리로드 없이 bfcache에서 페이지를 그대로 복원하므로 위 effect가 다시 실행되지 않는다.
    // pageshow의 persisted로 bfcache 복원을 감지해 그때도 세션을 다시 복구한다.
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
