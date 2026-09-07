import { BrowserRouter, Routes, Route } from 'react-router-dom'

import Layout from './components/layout/Layout.tsx'
import MainPage from './pages/Main/index.tsx'
import LoginPage from './pages/Login/index.tsx'
import UploadPage from './pages/Upload/index.tsx'
import QuestionPage from './pages/Question/index.tsx'
import JudgementPage from './pages/Judgement/index.tsx'
import ResultPage from './pages/Result/index.tsx'
import MyPage from './pages/Mypage/index.tsx'

function App() {

  return (
    <div className="">
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<MainPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/question" element={<QuestionPage />} />
            <Route path="/judgement" element={<JudgementPage />} />
            <Route path="/result" element={<ResultPage />} />
            <Route path="/mypage" element={<MyPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  )
}

export default App
