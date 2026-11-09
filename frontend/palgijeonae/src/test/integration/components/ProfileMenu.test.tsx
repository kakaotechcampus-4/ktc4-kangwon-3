import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import ProfileMenu from '@/components/common/ProfileMenu'
import { buildUserInfo } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { createGate } from '@/test/utils/createGate'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const MY_INFO_URL = `${API_URL}/api/v1/users/me`
const USER = buildUserInfo()

const renderProfileMenu = () => {
  const onLogout = vi.fn()
  renderWithProviders(<ProfileMenu onLogout={onLogout} />, { route: '/' })
  return { onLogout }
}

// 내 정보를 불러와 프로필 칩이 나타날 때까지 기다린다.
const findChip = () => screen.findByRole('button', { name: new RegExp(`${USER.name} 님`) })

const openMenu = async () => {
  const user = userEvent.setup()
  const chip = await findChip()
  await user.click(chip)
  return { user, chip }
}

describe('프로필 메뉴 - 불러오기', () => {
  it('내 정보를 불러오는 동안은 이름 없이 자리만 보여주고, 불러오면 이름 칩을 보여준다', async () => {
    const gate = createGate()
    server.use(
      http.get(MY_INFO_URL, async () => {
        await gate.promise
        return successResponse(USER)
      }),
    )
    renderProfileMenu()

    expect(screen.queryByRole('button')).not.toBeInTheDocument()

    gate.release()

    expect(await findChip()).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('프로필 메뉴 - 열고 닫기', () => {
  it('칩을 누르면 계정 정보와 메뉴가 열리고, 다시 누르면 닫힌다', async () => {
    renderProfileMenu()
    const { user, chip } = await openMenu()

    expect(chip).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(USER.email as string)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '마이페이지' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '로그아웃' })).toBeInTheDocument()

    await user.click(chip)

    expect(chip).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
  })

  it('소셜 계정에서 이메일을 받지 못한 회원에게는 안내 문구를 보여준다', async () => {
    server.use(http.get(MY_INFO_URL, () => successResponse(buildUserInfo({ email: null }))))
    renderProfileMenu()

    await openMenu()

    expect(screen.getByText('표시할 이메일이 없어요')).toBeInTheDocument()
  })

  it('Esc를 누르면 닫히고 칩으로 포커스가 돌아온다', async () => {
    renderProfileMenu()
    const { user, chip } = await openMenu()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
    expect(chip).toHaveFocus()
  })

  it('메뉴 바깥을 누르면 닫히지만, 메뉴 안의 계정 정보를 눌러서는 닫히지 않는다', async () => {
    renderProfileMenu()
    const { user } = await openMenu()

    await user.click(screen.getByText(USER.email as string))
    expect(screen.getByRole('link', { name: '마이페이지' })).toBeInTheDocument()

    await user.click(document.body)
    expect(screen.queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
  })
})

describe('프로필 메뉴 - 메뉴 선택', () => {
  it('마이페이지를 누르면 이동하고 메뉴가 닫힌다', async () => {
    renderProfileMenu()
    const { user } = await openMenu()

    await user.click(screen.getByRole('link', { name: '마이페이지' }))

    expect(getCurrentLocation()).toBe('/mypage')
    expect(screen.queryByRole('link', { name: '마이페이지' })).not.toBeInTheDocument()
  })

  it('로그아웃을 누르면 로그아웃을 요청하고 메뉴가 닫힌다', async () => {
    const { onLogout } = renderProfileMenu()
    const { user } = await openMenu()

    await user.click(screen.getByRole('button', { name: '로그아웃' }))

    expect(onLogout).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: '로그아웃' })).not.toBeInTheDocument()
  })
})
