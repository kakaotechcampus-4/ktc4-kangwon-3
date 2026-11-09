import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// 정책 페이지(이용약관·개인정보처리방침) 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = policyPage()
//   await page.clickTab('개인정보처리방침')
//   expect(page.tableCells()).toContain('Sentry')

type User = ReturnType<typeof userEvent.setup>

export function policyPage(user: User = userEvent.setup()) {
  const tabs = () => within(screen.getByRole('navigation', { name: '정책 문서' }))
  const tocLinks = () => within(screen.getByRole('navigation', { name: '목차' })).getAllByRole('link')

  return {
    // ── 화면 문구 ────────────────────────────────────────────
    hasHeading: (name: string) => screen.queryByRole('heading', { name }) !== null,
    hasText: (text: string) => screen.queryAllByText(text).length > 0,

    // ── 문서 탭 ──────────────────────────────────────────────
    clickTab: (name: string) => user.click(tabs().getByRole('link', { name })),
    isTabActive: (name: string) => tabs().getByRole('link', { name }).getAttribute('aria-current') === 'page',

    // ── 위탁 표 ──────────────────────────────────────────────
    hasTable: () => screen.queryByRole('table') !== null,
    /** 표 본문 칸의 글자를 왼쪽 위부터 차례로 */
    tableCells: () => within(screen.getByRole('table')).getAllByRole('cell').map((cell) => cell.textContent ?? ''),

    // ── 목차 ────────────────────────────────────────────────
    tocHeadings: () => tocLinks().map((link) => link.textContent ?? ''),
    tocTargets: () => tocLinks().map((link) => (link.getAttribute('href') ?? '').replace('#', '')),
    // NOTE(source): 조항 제목은 앵커 id가 붙은 section 안에 있어서 id로만 찾을 수 있다.
    // 소스에서 section에 aria-labelledby로 제목을 연결하면 getByRole('region', { name })으로 찾을 수 있다.
    hasSectionAnchor: (id: string) => document.getElementById(id) !== null,
  }
}

export type PolicyPage = ReturnType<typeof policyPage>
