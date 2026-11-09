import { Route } from 'react-router-dom'

import { POLICY_LINKS } from '@/constants/navigation'
import LoginPage from '@/pages/Login'
import { loginPage } from '@/test/drivers/loginPage'
import { setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

// 로그인 화면을 실제 라우터 위에서 사용자처럼 조작한다. 이동한 정책 페이지는 이 파일이 만든 스텁으로 대신한다.
const renderLoginPage = () => {
  setAuthState('loggedOut')
  renderWithProviders(<LoginPage />, {
    path: '/login',
    route: '/login',
    extraRoutes: <Route path="/policy/:type" element={<p>정책 화면</p>} />,
  })
  return loginPage()
}

describe('로그인 화면 - 약관 동의 안내', () => {
  it('이용약관 링크는 같은 탭에서 이용약관 페이지로 이동한다', async () => {
    const page = renderLoginPage()
    expect(page.termsHref()).toBe(POLICY_LINKS.terms.to)
    expect(page.opensInSameTab()).toBe(true)

    await page.clickTermsLink()

    expect(getCurrentLocation()).toBe('/policy/terms')
  })

  it('개인정보처리방침 링크는 같은 탭에서 개인정보처리방침 페이지로 이동한다', async () => {
    const page = renderLoginPage()
    expect(page.privacyHref()).toBe(POLICY_LINKS.privacy.to)
    expect(page.opensInSameTab()).toBe(true)

    await page.clickPrivacyLink()

    expect(getCurrentLocation()).toBe('/policy/privacy')
  })
})
