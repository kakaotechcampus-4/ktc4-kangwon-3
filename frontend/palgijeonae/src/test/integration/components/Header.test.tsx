import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import Header from '@/components/common/Header'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

const openMenu = async () => {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '메뉴 열기' }))
  return user
}

// 데스크톱용 로그인 버튼·프로필 칩도 jsdom에서는 CSS(hidden md:flex)가 적용되지 않아 함께 잡히므로, 메뉴 패널 안에서만 찾는다.
const getMenuPanel = () => {
  const panelId = screen.getByRole('button', { name: '메뉴 닫기' }).getAttribute('aria-controls')
  return within(document.getElementById(panelId as string) as HTMLElement)
}

const queryMenuNav = () => screen.queryByRole('navigation', { name: '주요 메뉴' })

describe('헤더 - 모바일 메뉴', () => {
  beforeEach(() => {
    setMobileViewport()
    setAuthState('loggedOut')
  })

  it('햄버거 버튼을 누르면 메뉴(메인, 상품 진단)가 열리고, 다시 누르면 닫힌다', async () => {
    renderWithProviders(<Header />)
    expect(queryMenuNav()).not.toBeInTheDocument()

    const user = await openMenu()

    expect(getMenuPanel().getByRole('link', { name: '메인' })).toBeInTheDocument()
    expect(getMenuPanel().getByRole('link', { name: '상품 진단' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '메뉴 닫기' })).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button', { name: '메뉴 닫기' }))

    expect(queryMenuNav()).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '메뉴 열기' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('메뉴가 열려 있는 동안 배경 스크롤을 잠그고, 닫으면 풀어 준다', async () => {
    renderWithProviders(<Header />)

    const user = await openMenu()
    expect(document.body.style.overflow).toBe('hidden')

    await user.click(screen.getByRole('button', { name: '메뉴 닫기' }))
    expect(document.body.style.overflow).toBe('')
  })

  it('메뉴를 눌러 다른 화면으로 이동하면 메뉴가 닫힌다', async () => {
    renderWithProviders(<Header />, { route: '/' })

    const user = await openMenu()
    await user.click(getMenuPanel().getByRole('link', { name: '상품 진단' }))

    expect(getCurrentLocation()).toBe('/upload')
    expect(queryMenuNav()).not.toBeInTheDocument()
  })

  it('이동했다가 처음 열었던 화면으로 돌아와도 메뉴가 저절로 열리지 않는다', async () => {
    renderWithProviders(<Header />, { route: '/' })

    const user = await openMenu()
    await user.click(getMenuPanel().getByRole('link', { name: '상품 진단' }))
    await user.click(screen.getByRole('link', { name: '사이트 로고' }))

    expect(getCurrentLocation()).toBe('/')
    expect(queryMenuNav()).not.toBeInTheDocument()
  })

  it('어두운 바깥 영역을 누르면 메뉴가 닫힌다', async () => {
    renderWithProviders(<Header />)

    const user = await openMenu()
    await user.click(screen.getByRole('presentation'))

    expect(queryMenuNav()).not.toBeInTheDocument()
  })

  it('Esc를 누르면 메뉴가 닫히고 포커스가 햄버거 버튼으로 돌아간다', async () => {
    renderWithProviders(<Header />)

    const user = await openMenu()
    await user.keyboard('{Escape}')

    expect(queryMenuNav()).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '메뉴 열기' })).toHaveFocus()
  })

  it('Tab으로 메뉴 안에서만 이동한다: 끝에서 Tab이면 햄버거 버튼으로, 햄버거 버튼에서 Shift+Tab이면 끝으로 간다', async () => {
    renderWithProviders(<Header />)

    const user = await openMenu()
    const loginButton = getMenuPanel().getByRole('button', { name: '로그인' })
    loginButton.focus()

    await user.tab()
    expect(screen.getByRole('button', { name: '메뉴 닫기' })).toHaveFocus()

    await user.tab({ shift: true })
    expect(loginButton).toHaveFocus()
  })

  it('로그인 전에는 메뉴에 로그인 버튼이 있고, 누르면 로그인 화면으로 이동하며 메뉴가 닫힌다', async () => {
    renderWithProviders(<Header />, { route: '/' })

    const user = await openMenu()
    expect(getMenuPanel().queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
    await user.click(getMenuPanel().getByRole('button', { name: '로그인' }))

    expect(getCurrentLocation()).toBe('/login')
    expect(queryMenuNav()).not.toBeInTheDocument()
  })

  it('인증 준비가 끝나기 전에는 메뉴에 회원 영역을 보여주지 않는다', async () => {
    setAuthState('restoring')
    renderWithProviders(<Header />)

    await openMenu()

    expect(getMenuPanel().queryByRole('button', { name: '로그인' })).not.toBeInTheDocument()
    expect(getMenuPanel().queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
  })

  it('로그인 후에는 이름·이메일과 마이페이지 링크, 로그아웃 버튼을 보여준다', async () => {
    setAuthState('loggedIn')
    renderWithProviders(<Header />, { route: '/' })

    const user = await openMenu()

    expect(await getMenuPanel().findByText('gildong@example.com')).toBeInTheDocument()
    expect(getMenuPanel().getByText('홍길동')).toBeInTheDocument()

    await user.click(getMenuPanel().getByRole('link', { name: '마이페이지' }))

    expect(getCurrentLocation()).toBe('/mypage')
    expect(queryMenuNav()).not.toBeInTheDocument()
  })

  it('메뉴에서 로그아웃하면 로그아웃을 요청하고 메인 화면으로 이동한다', async () => {
    setAuthState('loggedIn')
    server.use(
      http.post(`${API_URL}/api/v1/auth/logout`, async ({ request }) => {
        await recordRequest(request)
        return successResponse(null)
      }),
    )
    renderWithProviders(<Header />, { route: '/mypage' })

    const user = await openMenu()
    await user.click(await getMenuPanel().findByRole('button', { name: '로그아웃' }))

    await waitFor(() => expect(getCurrentLocation()).toBe('/'))
    expect(requestLog.find('POST', '/api/v1/auth/logout')).toHaveLength(1)
    expect(queryMenuNav()).not.toBeInTheDocument()
  })
})

describe('헤더 - 데스크톱', () => {
  it('데스크톱 폭에서는 햄버거 버튼을 눌러도 모바일 메뉴 패널을 열지 않는다', async () => {
    setAuthState('loggedOut')
    renderWithProviders(<Header />)

    await openMenu()

    expect(queryMenuNav()).not.toBeInTheDocument()
  })
})
