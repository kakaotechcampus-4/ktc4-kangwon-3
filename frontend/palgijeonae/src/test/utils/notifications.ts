import { waitFor } from '@testing-library/react'

// 화면이 사용자에게 알린 내용을 확인하는 헬퍼. 지금은 알림을 window.alert로 띄우므로 vitest.setup.ts의 alert 스텁을 읽는다.
// 알림 방식이 바뀌면(토스트 등) 테스트 본문은 두고 이 파일만 고친다. 테스트 본문에서 window.alert를 직접 단언하지 않는다.

// 문자열은 전체가 같아야 하고, RegExp는 일부만 맞아도 되며(g 플래그는 쓰지 않는다), { includes }는 그 문자열을 포함하면 된다.
export type NotificationMatcher = string | RegExp | { includes: string }

const receivedNotifications = (): string[] => vi.mocked(window.alert).mock.calls.map(([message]) => String(message))

const matches = (received: string, matcher: NotificationMatcher): boolean => {
  if (typeof matcher === 'string') {
    return received === matcher
  }
  if (matcher instanceof RegExp) {
    return matcher.test(received)
  }
  return received.includes(matcher.includes)
}

/** 그 내용으로 알렸는지 확인한다. */
export function expectNotified(message: NotificationMatcher): void {
  const received = receivedNotifications()
  expect(
    received.some((text) => matches(text, message)),
    `일치하는 알림이 없습니다. 기대: ${JSON.stringify(message)}, 받은 알림: ${JSON.stringify(received)}`,
  ).toBe(true)
}

/** 아무 알림도 띄우지 않았는지 확인한다. */
export function expectNotNotified(): void {
  expect(receivedNotifications(), '알림을 띄우지 않아야 하는데 띄웠습니다.').toEqual([])
}

/** 비동기 요청이 끝난 뒤에 알리는 경우, 그 알림이 뜰 때까지 기다린다. */
export async function waitForNotified(message: NotificationMatcher): Promise<void> {
  await waitFor(() => expectNotified(message))
}

/** 알림이 정해진 횟수만큼 뜰 때까지 기다린다. "실패해서 한 번 알린 뒤 다시 시도한다"처럼 내용보다 횟수가 중요한 흐름에 쓴다. */
export async function waitForNotificationCount(count: number): Promise<void> {
  await waitFor(() => expect(receivedNotifications()).toHaveLength(count))
}
