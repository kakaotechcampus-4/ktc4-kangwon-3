import { Route } from 'react-router-dom'

import ProtectedRoute from '@/components/common/ProtectedRoute'
import { POLICY_LINKS } from '@/constants/navigation'
import PolicyPage from '@/pages/Policy'
import { POLICY_DOCUMENTS } from '@/pages/Policy/constants'
import { POLICY_MESSAGES } from '@/test/constants/messages'
import { policyPage } from '@/test/drivers/policyPage'
import { type AuthScenario, setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderRoutes } from '@/test/utils/renderWithProviders'

const TERMS = POLICY_DOCUMENTS.terms
const PRIVACY = POLICY_DOCUMENTS.privacy

// 화면에 보이는 문구는 정책 문서 데이터에서 가져와 비교한다.
if (TERMS.summary.kind !== 'notice') {
  throw new Error('이용약관의 요약은 면책 안내(notice)여야 합니다.')
}
const TERMS_NOTICE = TERMS.summary

// App.tsx와 같은 구조: 정책 페이지는 ProtectedRoute 밖의 공개 라우트다.
const renderPolicyPage = (route: string) => {
  renderRoutes(
    <>
      <Route path="/login" element={<p>로그인 화면</p>} />
      <Route element={<ProtectedRoute />}>
        <Route path="/upload" element={<p>업로드 화면</p>} />
      </Route>
      <Route path="/policy/:type" element={<PolicyPage />} />
    </>,
    { route },
  )
  return policyPage()
}

describe('정책 페이지 - 이용약관', () => {
  it('/policy/terms에서 이용약관 제목과 시행일, 면책 요약을 보여준다', () => {
    const page = renderPolicyPage('/policy/terms')

    expect(page.hasHeading(TERMS.title)).toBe(true)
    expect(page.hasText(`시행일 ${TERMS.effectiveDate}`)).toBe(true)
    expect(page.hasText(TERMS_NOTICE.title)).toBe(true)
    TERMS_NOTICE.paragraphs.forEach((paragraph) => expect(page.hasText(paragraph)).toBe(true))
    expect(page.isTabActive(POLICY_LINKS.terms.label)).toBe(true)
  })

  it('이용약관에는 위탁 표가 없다', () => {
    const page = renderPolicyPage('/policy/terms')

    expect(page.hasTable()).toBe(false)
  })

  it('목차 항목이 본문 조항 제목과 같고, 각 목차 링크가 본문의 조항 위치를 가리킨다', () => {
    const page = renderPolicyPage('/policy/terms')

    expect(page.tocHeadings()).toEqual(TERMS.sections.map((section) => section.heading))
    expect(page.tocTargets()).toEqual(TERMS.sections.map((section) => section.id))
    TERMS.sections.forEach((section) => expect(page.hasSectionAnchor(section.id)).toBe(true))
  })
})

describe('정책 페이지 - 탭 이동', () => {
  it('개인정보처리방침 탭을 누르면 /policy/privacy로 이동해 방침 내용과 위탁 표를 보여준다', async () => {
    const page = renderPolicyPage('/policy/terms')

    await page.clickTab(POLICY_LINKS.privacy.label)

    expect(getCurrentLocation()).toBe('/policy/privacy')
    expect(page.hasHeading(PRIVACY.title)).toBe(true)
    expect(page.isTabActive(POLICY_LINKS.privacy.label)).toBe(true)
    expect(page.isTabActive(POLICY_LINKS.terms.label)).toBe(false)
    expect(page.hasHeading(TERMS.title)).toBe(false)

    const table = PRIVACY.sections.find((section) => section.table)?.table
    expect(table).toBeDefined()
    expect(page.tableCells()).toEqual((table?.rows ?? []).flat())
  })

  it('이용약관 탭을 다시 누르면 이용약관으로 돌아온다', async () => {
    const page = renderPolicyPage('/policy/privacy')

    await page.clickTab(POLICY_LINKS.terms.label)

    expect(getCurrentLocation()).toBe('/policy/terms')
    expect(page.hasHeading(TERMS.title)).toBe(true)
  })
})

describe('정책 페이지 - 잘못된 주소', () => {
  it('/policy/unknown처럼 없는 문서면 NotFound 화면을 보여준다', () => {
    const page = renderPolicyPage('/policy/unknown')

    expect(page.hasText(POLICY_MESSAGES.NOT_FOUND)).toBe(true)
    expect(page.hasHeading(TERMS.title)).toBe(false)
    expect(page.hasHeading(PRIVACY.title)).toBe(false)
  })
})

describe('정책 페이지 - 로그인 없이 접근', () => {
  it.each<AuthScenario>(['loggedOut', 'restoring'])('인증 상태가 %s여도 로그인 화면으로 보내지 않고 바로 보여준다', (scenario) => {
    setAuthState(scenario)

    const page = renderPolicyPage('/policy/terms')

    expect(getCurrentLocation()).toBe('/policy/terms')
    expect(page.hasHeading(TERMS.title)).toBe(true)
  })
})
