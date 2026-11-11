import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { JUDGEMENT_MESSAGES } from '@/test/constants/messages'

// 진단 진행 화면 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = judgementPage()
//   await page.waitUntilLoaded()
//   expect(page.card('완료 상품').resultLinkHref()).toBe('/result/product/p3')

type User = ReturnType<typeof userEvent.setup>

export function judgementPage(user: User = userEvent.setup()) {
  const productList = () => screen.getByRole('list', { name: '진단 중인 상품' })

  // NOTE(source): 상품 카드에는 이름(aria-labelledby 등)이 없어서 이름으로 직접 찾을 수 없다.
  // 상품 목록 안의 listitem 중 제목 heading을 가진 항목을 카드로 본다. (진행 단계 막대의 listitem에는 heading이 없어 섞이지 않는다)
  // 소스에서 카드에 aria-labelledby로 제목을 연결하면 getByRole('listitem', { name })으로 바로 찾을 수 있다.
  const cardElements = () =>
    within(productList())
      .getAllByRole('listitem')
      .filter((item) => within(item).queryByRole('heading') !== null)
  const nameOf = (item: HTMLElement) => within(item).getByRole('heading').textContent?.trim() ?? ''

  const findCard = (name: string): HTMLElement => {
    const item = cardElements().find((candidate) => nameOf(candidate) === name)
    if (!item) {
      throw new Error(`"${name}" 카드를 찾을 수 없습니다. 현재 목록: ${JSON.stringify(cardElements().map(nameOf))}`)
    }
    return item
  }

  // 이름이 같은 카드 하나에 대한 조작·조회. 폴링으로 화면이 갱신되어도 호출할 때마다 카드를 다시 찾는다.
  const card = (name: string) => {
    const scope = () => within(findCard(name))
    const linkHref = (linkName: RegExp) => scope().queryByRole('link', { name: linkName })?.getAttribute('href') ?? null

    return {
      /** 카드 안에서 그 문구가 몇 번 보이는지 (설명 줄과 안내 박스에 같은 문구가 나올 수 있다) */
      textCount: (text: string) => scope().queryAllByText(text).length,
      hasText: (text: string) => scope().queryAllByText(text).length > 0,
      /** 상태 배지의 라벨(진행 중/답변 필요/완료/실패) */
      hasStatusLabel: (label: string) => scope().queryAllByText(label).length > 0,

      hasProgressSteps: () => scope().queryByRole('list', { name: '진단 단계' }) !== null,
      /** 진행 단계 막대에서 현재 단계(aria-current)의 글자. 없으면 null */
      currentStep() {
        const steps = scope().getByRole('list', { name: '진단 단계' })
        const current = within(steps)
          .getAllByRole('listitem')
          .find((step) => step.getAttribute('aria-current') === 'step')
        return current?.textContent ?? null
      },

      hasAnyLink: () => scope().queryAllByRole('link').length > 0,
      answerLinkHref: () => linkHref(/질문에 답변하기/),
      resultLinkHref: () => linkHref(/결과 보기/),
      goToQuestion: () => user.click(scope().getByRole('link', { name: /질문에 답변하기/ })),
      goToResult: () => user.click(scope().getByRole('link', { name: /결과 보기/ })),
    }
  }

  const reportButton = () => screen.getByRole('button', { name: /진단서 보기/ })

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    waitUntilLoaded: () => screen.findByRole('list', { name: '진단 중인 상품' }),
    isLoading: () => screen.queryByRole('status', { name: /로딩/ }) !== null,
    clickRetry: () => user.click(screen.getByRole('button', { name: /다시 시도/ })),

    // ── 화면 문구 ────────────────────────────────────────────
    hasMessage: (text: string) => screen.queryByText(text) !== null,
    /** 그 문구가 화면에 나올 때까지 기다린다. */
    waitForMessage: async (text: string) => {
      await screen.findByText(text)
    },
    hasProductCountIntro: (count: number) =>
      screen.queryByText((content) => content.startsWith(JUDGEMENT_MESSAGES.productCountIntro(count))) !== null,

    // ── 카드 ────────────────────────────────────────────────
    productNames: () => cardElements().map(nameOf),
    card,

    // ── 진단서 보기 ──────────────────────────────────────────
    hasReportButton: () => screen.queryByRole('button', { name: /진단서 보기/ }) !== null,
    /** 진단이 끝나 진단서로 이동할 수 있는지. (끝나기 전에는 aria-disabled이고, 눌러도 이동하지 않는다) */
    isReportEnabled: () => reportButton().getAttribute('aria-disabled') !== 'true',
    openReport: () => user.click(reportButton()),
    /** 하단 바의 "완료 n / m" 요약이 보이는지. 예: hasReportProgress(2, 3) */
    hasReportProgress: (ended: number, total: number) => screen.queryByText(JUDGEMENT_MESSAGES.reportProgress(ended, total)) !== null,

    // ── 스크린리더 안내 ───────────────────────────────────────
    // NOTE(source): 상태 변화 안내는 화면에 보이지 않는 live region(role="status")이다. 이름이 없고, 불러온 뒤에는 이 화면의 유일한 status라서
    // role만으로 찾는다. 불러오는 중에는 로딩 표시도 status라 두 개가 되므로 불러온 뒤에 쓴다. 소스에서 이름(aria-label)을 붙이면 구분할 수 있다.
    announcement: () => screen.getByRole('status').textContent ?? '',
    waitForAnnouncement: (text: string) => waitFor(() => expect(screen.getByRole('status').textContent ?? '').toContain(text)),
  }
}

export type JudgementPage = ReturnType<typeof judgementPage>
