import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProcessingStatusType } from '@/api/types/common'
import ProductProgressCard from '@/pages/Judgement/components/ProductProgressCard'
import { buildProductResult } from '@/test/mocks/fixtures'
import { renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

// 40글자: 데스크톱 글자 수 한도(30)를 넘는다.
const LONG_NAME = '가'.repeat(40)

const renderCard = (productName: string) =>
  renderWithProviders(
    <ProductProgressCard product={buildProductResult({ productName, processingStatus: ProcessingStatusType.InProgress })} />,
  )

describe('진행 카드 - 상품명 말줄임', () => {
  it('데스크톱에서는 30글자까지만 보여주고 ...를 붙이며, 전체 이름을 title 속성으로 남긴다', () => {
    renderCard(LONG_NAME)

    const name = screen.getByRole('heading', { level: 2 })
    expect(name).toHaveTextContent(`${'가'.repeat(30)}...`)
    expect(name).toHaveAttribute('title', LONG_NAME)
  })

  it('데스크톱에서 자르지 않은 이름에는 title 속성을 달지 않는다', () => {
    renderCard('가'.repeat(30))

    expect(screen.getByRole('heading', { level: 2 })).not.toHaveAttribute('title')
  })

  it('모바일에서는 글자 수로 자르지 않고 원본 이름을 넘기며(CSS가 한 줄로 자름), 전체 이름을 title 속성으로 남긴다', () => {
    setMobileViewport()
    renderCard(LONG_NAME)

    const name = screen.getByRole('heading', { level: 2 })
    expect(name).toHaveTextContent(LONG_NAME)
    expect(name).not.toHaveTextContent('...')
    expect(name).toHaveAttribute('title', LONG_NAME)
  })
})
