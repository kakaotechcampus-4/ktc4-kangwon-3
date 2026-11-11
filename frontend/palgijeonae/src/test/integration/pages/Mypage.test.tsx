import { screen } from '@testing-library/react'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import MyPage from '@/pages/Mypage'
import { useAuthStore } from '@/store/useAuthStore'
import { MYPAGE_MESSAGES, SERVER_MESSAGES } from '@/test/constants/messages'
import { myPage } from '@/test/drivers/myPage'
import { buildUserInfo } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { setAuthState } from '@/test/utils/auth'
import { declineConfirm, expectConfirmed } from '@/test/utils/confirmations'
import { createGate } from '@/test/utils/createGate'
import { expectNotified, waitForNotified } from '@/test/utils/notifications'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const MY_INFO_URL = `${API_URL}/api/v1/users/me`
const NOTIFICATION_SETTINGS_URL = `${API_URL}/api/v1/users/me/notification-settings`

// 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const USER = buildUserInfo()
const NEW_NAME = '김철수'

// 마이페이지를 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(myPage)를 거친다.
const renderMyPage = () => {
  const { queryClient } = renderWithProviders(<MyPage />, {
    path: '/mypage',
    route: '/mypage',
    extraRoutes: <Route path="/" element={<p>메인 화면</p>} />,
  })
  return { page: myPage(), queryClient }
}

// 이동한 도착 화면(이 파일이 만든 스텁)이 보일 때까지 기다린다.
const findStubScreen = (text: string) => screen.findByText(text)

describe('마이페이지 - 조회', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 회원 정보를 보여준다', async () => {
    const { page } = renderMyPage()

    expect(page.loadingIndicatorCount()).toBe(1)

    await page.waitForUserName(USER.name)
    expect(page.hasText(USER.email as string)).toBe(true)
    expect(page.hasText(MYPAGE_MESSAGES.joinedWith(USER.socialProvider))).toBe(true)
    expect(page.loadingIndicatorCount()).toBe(0)
  })

  it('마이페이지에서 상품 목록과 개정 알림을 조회하지 않는다', async () => {
    const { page } = renderMyPage()
    await page.waitForUserName(USER.name)

    expect(requestLog.find('GET', '/api/v1/products')).toHaveLength(0)
    expect(requestLog.find('GET', '/api/v1/law-amendments')).toHaveLength(0)
  })

  it('회원 정보 조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    server.use(http.get(MY_INFO_URL, () => errorResponse(500), { once: true }))
    const { page } = renderMyPage()

    await page.waitForText(MYPAGE_MESSAGES.PROFILE_LOAD_FAILED)

    await page.clickRetry()

    await page.waitForUserName(USER.name)
  })
})

describe('마이페이지 - 이름 수정', () => {
  const renderProfile = async () => {
    const { page } = renderMyPage()
    await page.waitForUserName(USER.name)
    return page
  }

  it('수정 버튼을 누르면 현재 이름이 채워진 입력창으로 바뀐다', async () => {
    const page = await renderProfile()

    await page.startEditingName()

    expect(page.nameInputValue()).toBe(USER.name)
    expect(page.isNameInputFocused()).toBe(true)
    expect(page.hasSaveButton()).toBe(true)
    expect(page.hasCancelButton()).toBe(true)
  })

  it('새 이름을 저장하면 요청을 보내고, 화면에 새 이름이 보이며 편집이 끝난다', async () => {
    const page = await renderProfile()
    await page.startEditingName()

    await page.replaceName(NEW_NAME)
    await page.saveName()

    await page.waitForUserName(NEW_NAME)
    expect(page.hasUserName(USER.name)).toBe(false)
    expect(page.hasEditNameButton()).toBe(true)
    expect(requestLog.find('PATCH', '/api/v1/users/me')[0].body).toEqual({ name: NEW_NAME })
  })

  it('이름 앞뒤 공백은 지워서 저장한다', async () => {
    const page = await renderProfile()
    await page.startEditingName()

    await page.replaceName(`  ${NEW_NAME}  `)
    await page.saveName()

    await page.waitForUserName(NEW_NAME)
    expect(requestLog.find('PATCH', '/api/v1/users/me')[0].body).toEqual({ name: NEW_NAME })
  })

  it('이름이 그대로면 요청 없이 편집만 끝낸다', async () => {
    const page = await renderProfile()
    await page.startEditingName()

    await page.saveName()

    expect(page.hasEditNameButton()).toBe(true)
    expect(requestLog.find('PATCH', '/api/v1/users/me')).toHaveLength(0)
  })

  it('이름을 비우거나 20자를 넘기면 저장 버튼을 비활성화한다', async () => {
    const page = await renderProfile()
    await page.startEditingName()

    await page.clearName()
    expect(page.isSaveEnabled()).toBe(false)

    await page.replaceName('가'.repeat(20))
    expect(page.hasText(MYPAGE_MESSAGES.nameLength(20))).toBe(true)
    expect(page.isSaveEnabled()).toBe(true)

    await page.replaceName('가'.repeat(21))
    expect(page.hasText(MYPAGE_MESSAGES.nameLength(21))).toBe(true)
    expect(page.isSaveEnabled()).toBe(false)
  })

  it('공백만 입력해도 저장 버튼을 비활성화한다', async () => {
    const page = await renderProfile()
    await page.startEditingName()

    await page.replaceName('     ')

    expect(page.isSaveEnabled()).toBe(false)
  })

  it('취소하면 고치던 내용을 버리고 원래 이름으로 돌아가며 요청도 보내지 않는다', async () => {
    const page = await renderProfile()
    await page.startEditingName()
    await page.replaceName(NEW_NAME)

    await page.cancelEditName()

    expect(page.hasUserName(USER.name)).toBe(true)
    expect(requestLog.find('PATCH', '/api/v1/users/me')).toHaveLength(0)

    // 다시 수정을 시작하면 고치던 내용이 아니라 원래 이름이 채워진다.
    await page.startEditingName()
    expect(page.nameInputValue()).toBe(USER.name)
  })

  it('Esc를 누르면 편집을 취소한다', async () => {
    const page = await renderProfile()
    await page.startEditingName()
    await page.replaceName(NEW_NAME)

    await page.pressEscape()

    expect(page.hasUserName(USER.name)).toBe(true)
    expect(page.isEditingName()).toBe(false)
  })

  it('저장하는 동안에는 입력창과 버튼을 비활성화하고, 끝나면 편집이 닫힌다', async () => {
    const gate = createGate()
    server.use(
      http.patch(MY_INFO_URL, async ({ request }) => {
        const { name } = await recordRequest<{ name: string }>(request)
        await gate.promise
        return successResponse(buildUserInfo({ name }))
      }),
    )
    const page = await renderProfile()
    await page.startEditingName()
    await page.replaceName(NEW_NAME)

    await page.saveName()

    await page.waitUntilNameInputDisabled()
    expect(page.isSaveEnabled()).toBe(false)
    expect(page.isCancelEnabled()).toBe(false)

    gate.release()

    await page.waitForUserName(NEW_NAME)
    expect(page.isEditingName()).toBe(false)
  })

  it('저장에 실패하면 서버의 오류 메시지를 안내하고, 편집 중인 상태와 입력한 이름을 유지한다', async () => {
    server.use(http.patch(MY_INFO_URL, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.NAME_TAKEN })))
    const page = await renderProfile()
    await page.startEditingName()
    await page.replaceName(NEW_NAME)

    await page.saveName()

    await waitForNotified(SERVER_MESSAGES.NAME_TAKEN)
    expect(page.nameInputValue()).toBe(NEW_NAME)
    expect(page.isSaveEnabled()).toBe(true)
    expect(page.hasUserName(USER.name)).toBe(false)
  })
})

describe('마이페이지 - 회원 탈퇴', () => {
  const renderLoggedInPage = async () => {
    setAuthState('loggedIn')
    const view = renderMyPage()
    await view.page.waitForUserName(USER.name)
    return view
  }

  it('탈퇴하기를 누르면 삭제되는 데이터를 알리는 확인 문구를 보여준다', async () => {
    const { page } = await renderLoggedInPage()

    await page.clickWithdraw()

    expectConfirmed({ includes: MYPAGE_MESSAGES.WITHDRAW_CONFIRM_TITLE })
    expectConfirmed({ includes: MYPAGE_MESSAGES.WITHDRAW_CONFIRM_DATA })
  })

  it('확인을 취소하면 요청을 보내지 않고 로그인 상태도 그대로다', async () => {
    declineConfirm()
    const { page } = await renderLoggedInPage()

    await page.clickWithdraw()

    expect(requestLog.find('DELETE', '/api/v1/users/me')).toHaveLength(0)
    expect(useAuthStore.getState().isLoggedIn).toBe(true)
    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('탈퇴에 성공하면 메인으로 이동하고, 로그아웃하며 캐시를 비우고 완료를 안내한다', async () => {
    const { page, queryClient } = await renderLoggedInPage()

    await page.clickWithdraw()

    expect(await findStubScreen('메인 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/')
    expect(requestLog.find('DELETE', '/api/v1/users/me')).toHaveLength(1)
    expect(useAuthStore.getState()).toMatchObject({ isLoggedIn: false, accessToken: null })
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expectNotified(MYPAGE_MESSAGES.WITHDRAW_DONE)
  })

  it('탈퇴하는 동안에는 버튼을 "탈퇴 중"으로 비활성화한다', async () => {
    const gate = createGate()
    server.use(
      http.delete(MY_INFO_URL, async () => {
        await gate.promise
        return successResponse(null)
      }),
    )
    const { page } = await renderLoggedInPage()

    await page.clickWithdraw()

    await page.waitUntilWithdrawing()
    expect(page.isWithdrawing()).toBe(true)

    gate.release()

    expect(await findStubScreen('메인 화면')).toBeInTheDocument()
  })

  it('탈퇴에 실패하면 서버의 오류 메시지를 안내하고, 화면과 로그인 상태를 그대로 둔다', async () => {
    server.use(http.delete(MY_INFO_URL, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.WITHDRAW_BLOCKED })))
    const { page } = await renderLoggedInPage()

    await page.clickWithdraw()

    await waitForNotified(SERVER_MESSAGES.WITHDRAW_BLOCKED)
    expect(getCurrentLocation()).toBe('/mypage')
    expect(useAuthStore.getState().isLoggedIn).toBe(true)
    expect(page.isWithdrawEnabled()).toBe(true)
  })
})

describe('마이페이지 - 알림 설정', () => {
  it('법령 개정 알림 토글을 누르면 변경한 값을 서버에 보내고 토글 상태가 바뀐다', async () => {
    const { page } = renderMyPage()
    await page.waitForAlertSettingsLoaded()
    expect(page.isLawAmendmentAlertOn()).toBe(true)

    await page.toggleLawAmendmentAlert()

    await page.waitForLawAmendmentAlert(false)
    expect(requestLog.find('PATCH', '/api/v1/users/me/notification-settings').map((entry) => entry.body)).toEqual([{ lawAmendmentAlertEnabled: false }])
  })

  it('알림 설정을 바꾸지 못하면 서버의 오류 메시지를 안내하고, 토글 상태를 그대로 둔다', async () => {
    server.use(http.patch(NOTIFICATION_SETTINGS_URL, () => errorResponse(500, { detailMessage: SERVER_MESSAGES.NOTIFICATION_NOT_SAVED })))
    const { page } = renderMyPage()
    await page.waitForAlertSettingsLoaded()

    await page.toggleLawAmendmentAlert()

    await waitForNotified(SERVER_MESSAGES.NOTIFICATION_NOT_SAVED)
    expect(page.isLawAmendmentAlertOn()).toBe(true)
  })
})
