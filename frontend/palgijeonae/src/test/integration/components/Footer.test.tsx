import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import Footer from '@/components/common/Footer'
import { CONTACT_EMAIL, FOOTER_NAV_ITEMS, GITHUB_URL, POLICY_LINKS } from '@/constants/navigation'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

const getContactLink = () => screen.getByRole('link', { name: CONTACT_EMAIL })

describe('푸터 - 메뉴', () => {
  it.each(FOOTER_NAV_ITEMS)('"$label" 메뉴를 누르면 $to로 이동한다', async ({ label, to }) => {
    const user = userEvent.setup()
    renderWithProviders(<Footer />, { route: '/policy/terms' })

    await user.click(within(screen.getByRole('navigation', { name: '푸터 메뉴' })).getByRole('link', { name: label }))

    expect(getCurrentLocation()).toBe(to)
  })
})

describe('푸터 - 링크', () => {
  it('이용약관과 개인정보처리방침 링크가 정책 페이지를 가리킨다', () => {
    renderWithProviders(<Footer />)

    expect(screen.getByRole('link', { name: POLICY_LINKS.terms.label })).toHaveAttribute('href', '/policy/terms')
    expect(screen.getByRole('link', { name: POLICY_LINKS.privacy.label })).toHaveAttribute('href', '/policy/privacy')
  })

  it('정책 링크를 누르면 해당 정책 페이지로 이동한다', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Footer />)

    await user.click(screen.getByRole('link', { name: POLICY_LINKS.privacy.label }))

    expect(getCurrentLocation()).toBe('/policy/privacy')
  })

  it('문의 링크는 메일 주소를 보여주고 mailto로 연결된다', () => {
    renderWithProviders(<Footer />)

    expect(getContactLink()).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`)
  })

  it('GitHub 링크는 새 탭으로 열린다', () => {
    renderWithProviders(<Footer />)

    const github = screen.getByRole('link', { name: 'GitHub' })
    expect(github).toHaveAttribute('href', GITHUB_URL)
    expect(github).toHaveAttribute('target', '_blank')
    expect(github).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

describe('푸터 - 모바일', () => {
  it('모바일에서도 문의·GitHub·정책 링크를 한 번씩만 보여준다', () => {
    setMobileViewport()
    renderWithProviders(<Footer />)

    expect(screen.getAllByRole('link', { name: CONTACT_EMAIL })).toHaveLength(1)
    expect(getContactLink()).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`)
    expect(screen.getAllByRole('link', { name: 'GitHub' })).toHaveLength(1)
    expect(screen.getByRole('link', { name: POLICY_LINKS.terms.label })).toHaveAttribute('href', '/policy/terms')
    expect(screen.getByRole('link', { name: POLICY_LINKS.privacy.label })).toHaveAttribute('href', '/policy/privacy')
  })
})
