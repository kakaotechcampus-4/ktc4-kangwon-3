import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ReturnPathGuide from '@/pages/Main/components/HowToUse/components/ReturnPathGuide'
import { renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

// 강조(굵은 글씨) 단어만 따로 잡고, 그 단어를 품은 문장 전체는 부모 요소의 글자로 확인한다.
const getFirstRowSentence = (emphasis: string) => screen.getByText(emphasis, { selector: 'b' }).parentElement

describe('메인 사용 방법 - 화면을 떠났다면 돌아오는 방법', () => {
  it('데스크톱에서는 오른쪽 위 프로필을 눌러 마이페이지를 고르라고 안내한다', () => {
    renderWithProviders(<ReturnPathGuide />)

    expect(getFirstRowSentence('프로필')).toHaveTextContent('오른쪽 위 프로필을 눌러 마이페이지 선택')
    expect(screen.queryByText('메뉴', { selector: 'b' })).not.toBeInTheDocument()
    expect(screen.getByText('홍길동 님')).toBeInTheDocument()
  })

  it('모바일에서는 오른쪽 위 메뉴(햄버거)를 눌러 마이페이지를 고르라고 안내하고, 프로필 칩 대신 햄버거 아이콘을 보여준다', () => {
    setMobileViewport()
    renderWithProviders(<ReturnPathGuide />)

    expect(getFirstRowSentence('메뉴')).toHaveTextContent('오른쪽 위 메뉴를 눌러 마이페이지 선택')
    expect(screen.queryByText('프로필', { selector: 'b' })).not.toBeInTheDocument()
    expect(screen.queryByText('홍길동 님')).not.toBeInTheDocument()
  })
})
