import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { POLICY_LINKS } from '@/constants/navigation'

// 로그인 화면 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = loginPage()
//   await page.clickTermsLink()

type User = ReturnType<typeof userEvent.setup>

export function loginPage(user: User = userEvent.setup()) {
  // 약관 동의 안내 문장 안의 두 링크. 이름은 푸터와 같은 정책 링크 상수를 쓴다.
  const termsLink = () => screen.getByRole('link', { name: POLICY_LINKS.terms.label })
  const privacyLink = () => screen.getByRole('link', { name: POLICY_LINKS.privacy.label })

  return {
    termsHref: () => termsLink().getAttribute('href'),
    privacyHref: () => privacyLink().getAttribute('href'),
    /** 같은 탭에서 열리는지 (새 탭으로 열리면 target이 지정된다) */
    opensInSameTab: () => termsLink().getAttribute('target') === null && privacyLink().getAttribute('target') === null,
    clickTermsLink: () => user.click(termsLink()),
    clickPrivacyLink: () => user.click(privacyLink()),
  }
}

export type LoginPage = ReturnType<typeof loginPage>
