import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ReturnPathGuide from '@/pages/Main/components/HowToUse/components/ReturnPathGuide'
import { renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

// 강조(굵은 글씨) 단어만 따로 잡고, 그 단어를 품은 문장 전체는 부모 요소의 글자로 확인한다.
const getFirstRowSentence = (emphasis: string) => screen.getByText(emphasis, { selector: 'b' }).parentElement

describe('메인 사용 방법 - 화면을 떠났다면 돌아오는 방법', () => {
  it('데스크톱에서는 위쪽 메뉴에서 진단 결과를 고르라고 안내하고, 미리보기에서 「진단 결과」를 강조한다', () => {
    renderWithProviders(<ReturnPathGuide />)

    expect(getFirstRowSentence('메뉴')).toHaveTextContent('위쪽 메뉴에서 진단 결과 선택')
    expect(screen.getByText('진단 결과', { selector: 'span' })).toHaveClass('font-bold', 'ring-4')
    expect(screen.queryByText('홍길동 님')).not.toBeInTheDocument()
  })

  it('모바일에서는 오른쪽 위 메뉴(햄버거)를 눌러 진단 결과를 고르라고 안내하고, 메뉴 글자 대신 햄버거 아이콘을 보여준다', () => {
    setMobileViewport()
    renderWithProviders(<ReturnPathGuide />)

    expect(getFirstRowSentence('메뉴')).toHaveTextContent('오른쪽 위 메뉴를 눌러 진단 결과 선택')
    expect(screen.queryByText('진단 결과', { selector: 'span' })).not.toBeInTheDocument()
  })
})
