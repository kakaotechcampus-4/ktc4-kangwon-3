import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// 마이페이지 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = myPage()
//   await page.waitForUserName('홍길동')
//   await page.startEditingName()

type User = ReturnType<typeof userEvent.setup>

export function myPage(user: User = userEvent.setup()) {
  // ── 알림 설정 ───────────────────────────────────────────────
  const alertSwitch = () => screen.getByRole('switch', { name: /법령 개정 알림/ })

  // ── 회원 정보 ───────────────────────────────────────────────
  const nameInput = () => screen.getByLabelText(/^이름$/)
  const saveButton = () => screen.getByRole('button', { name: /^저장$/ })
  const cancelButton = () => screen.getByRole('button', { name: /^취소$/ })

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    /** 회원 정보의 로딩 표시가 몇 개 보이는지 */
    loadingIndicatorCount: () => screen.queryAllByRole('status', { name: /로딩/ }).length,
    /** 불러오기 실패 화면의 "다시 시도"를 누른다. */
    clickRetry: () => user.click(screen.getByRole('button', { name: /다시 시도/ })),

    // ── 화면 문구 ────────────────────────────────────────────
    hasText: (text: string) => screen.queryAllByText(text).length > 0,
    waitForText: async (text: string) => {
      await screen.findByText(text)
    },

    // ── 회원 정보 ────────────────────────────────────────────
    hasUserName: (name: string) => screen.queryAllByText(name).length > 0,
    waitForUserName: async (name: string) => {
      await screen.findByText(name)
    },

    // ── 이름 수정 ────────────────────────────────────────────
    startEditingName: () => user.click(screen.getByRole('button', { name: /이름 수정/ })),
    hasEditNameButton: () => screen.queryByRole('button', { name: /이름 수정/ }) !== null,
    isEditingName: () => screen.queryByLabelText(/^이름$/) !== null,
    nameInputValue: () => (nameInput() as HTMLInputElement).value,
    isNameInputFocused: () => document.activeElement === nameInput(),
    isNameInputEnabled: () => !(nameInput() as HTMLInputElement).disabled,
    waitUntilNameInputDisabled: () => waitFor(() => expect((nameInput() as HTMLInputElement).disabled).toBe(true)),
    /** 입력창의 이름을 모두 지운다. */
    clearName: () => user.clear(nameInput()),
    /** 입력창의 이름을 지우고 새 이름을 붙여 넣는다. */
    async replaceName(name: string) {
      await user.clear(nameInput())
      await user.paste(name)
    },
    saveName: () => user.click(saveButton()),
    cancelEditName: () => user.click(cancelButton()),
    pressEscape: () => user.keyboard('{Escape}'),
    hasSaveButton: () => screen.queryByRole('button', { name: /^저장$/ }) !== null,
    hasCancelButton: () => screen.queryByRole('button', { name: /^취소$/ }) !== null,
    isSaveEnabled: () => !(saveButton() as HTMLButtonElement).disabled,
    isCancelEnabled: () => !(cancelButton() as HTMLButtonElement).disabled,

    // ── 알림 설정 ────────────────────────────────────────────
    waitForAlertSettingsLoaded: () => waitFor(() => expect(alertSwitch()).toBeEnabled()),
    isLawAmendmentAlertOn: () => alertSwitch().getAttribute('aria-checked') === 'true',
    toggleLawAmendmentAlert: () => user.click(alertSwitch()),
    waitForLawAmendmentAlert: (on: boolean) => waitFor(() => expect(alertSwitch().getAttribute('aria-checked')).toBe(String(on))),

    // ── 회원 탈퇴 ────────────────────────────────────────────
    clickWithdraw: () => user.click(screen.getByRole('button', { name: /^탈퇴하기$/ })),
    /** 탈퇴 요청이 진행 중이라 버튼이 "탈퇴 중"으로 바뀌어 비활성화되었는지 */
    isWithdrawing() {
      const button = screen.queryByRole('button', { name: /탈퇴 중/ })
      return button !== null && (button as HTMLButtonElement).disabled
    },
    waitUntilWithdrawing: async () => {
      await screen.findByRole('button', { name: /탈퇴 중/ })
    },
    isWithdrawEnabled() {
      const button = screen.queryByRole('button', { name: /^탈퇴하기$/ })
      return button !== null && !(button as HTMLButtonElement).disabled
    },
  }
}

export type MyPage = ReturnType<typeof myPage>
