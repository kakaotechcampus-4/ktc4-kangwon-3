import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProcessingStatusType, SourceType } from '@/api/types/common'
import ProductPreview from '@/components/common/ProductPreview'
import { setMobileViewport } from '@/test/utils/viewport'

// 30글자: 데스크톱 한도(40)는 넘지 않고 모바일 한도(24)는 넘는다.
const NAME_30 = '가'.repeat(30)

const renderPreview = (productName: string) =>
  render(
    <ProductPreview
      productName={productName}
      resultStatus={null}
      processingStatus={ProcessingStatusType.InProgress}
      sourceType={SourceType.Url}
    />,
  )

describe('ProductPreview - 제목 말줄임', () => {
  it('데스크톱에서는 40글자까지 그대로 보여주고, 자르지 않았으면 title 속성을 달지 않는다', () => {
    renderPreview(NAME_30)

    const title = screen.getByRole('heading', { name: NAME_30 })
    expect(title).not.toHaveAttribute('title')
  })

  it('모바일에서는 24글자까지 보여주고 넘으면 ...를 붙이며, 전체 이름을 title 속성으로 남긴다', () => {
    setMobileViewport()
    renderPreview(NAME_30)

    const title = screen.getByRole('heading', { name: `${'가'.repeat(24)}...` })
    expect(title).toHaveAttribute('title', NAME_30)
  })

  it('실제로 잘린 경우에만 title 속성을 단다: 모바일이어도 24글자 이하면 달지 않는다', () => {
    setMobileViewport()
    renderPreview('가'.repeat(24))

    expect(screen.getByRole('heading', { name: '가'.repeat(24) })).not.toHaveAttribute('title')
  })
})
