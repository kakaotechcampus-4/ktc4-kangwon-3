import { matchesMessage, type NotificationMatcher } from './notifications'

// 삭제·탈퇴처럼 사용자에게 확인을 받는 흐름을 다루는 헬퍼. 지금은 window.confirm을 쓰므로 vitest.setup.ts의 confirm 스텁(기본: 확인)을 읽는다.
// 확인 방식이 바뀌면(모달 등) 테스트 본문은 두고 이 파일만 고친다. 테스트 본문에서 window.confirm을 직접 다루지 않는다.

const receivedConfirmations = (): string[] => vi.mocked(window.confirm).mock.calls.map(([message]) => String(message))

/** 그 내용으로 사용자에게 확인을 요청했는지 확인한다. (문자열은 전체 일치, RegExp·{ includes }는 일부 일치) */
export function expectConfirmed(message: NotificationMatcher): void {
  const received = receivedConfirmations()
  expect(
    received.some((text) => matchesMessage(text, message)),
    `일치하는 확인 요청이 없습니다. 기대: ${JSON.stringify(message)}, 받은 요청: ${JSON.stringify(received)}`,
  ).toBe(true)
}

/** 이후 확인 요청에 사용자가 "취소"를 누른 것으로 만든다. (기본은 "확인") */
export function declineConfirm(): void {
  vi.mocked(window.confirm).mockReturnValue(false)
}
