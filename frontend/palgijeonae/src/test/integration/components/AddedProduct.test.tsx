import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SourceType } from '@/api/types/common'
import AddedProduct from '@/pages/Upload/components/AddedProduct'
import { setMobileViewport } from '@/test/utils/viewport'

// 30글자: 데스크톱 한도(40)는 넘지 않는다. 50글자: 데스크톱 한도를 넘는다.
const NAME_30 = '가'.repeat(30)
const NAME_50 = '가'.repeat(50)

const renderProduct = (title: string) => render(<AddedProduct type={SourceType.Url} title={title} onRemove={() => {}} />)

describe('추가된 상품 카드 - 제목 말줄임', () => {
  it('데스크톱에서는 40글자까지 그대로 보여주고, 자르지 않았으면 title 속성을 달지 않는다', () => {
    renderProduct(NAME_30)

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(NAME_30)
    expect(screen.getByRole('heading', { level: 3 })).not.toHaveAttribute('title')
  })

  it('데스크톱에서는 40글자를 넘으면 40글자 뒤에 ...를 붙이고, 전체 이름을 title 속성으로 남긴다', () => {
    renderProduct(NAME_50)

    const title = screen.getByRole('heading', { level: 3 })
    expect(title).toHaveTextContent(`${'가'.repeat(40)}...`)
    expect(title).toHaveAttribute('title', NAME_50)
  })

  it('모바일에서는 글자 수로 자르지 않고 원본 제목을 넘기며(CSS가 한 줄에서 자름), 전체 이름을 title 속성으로 남긴다', () => {
    setMobileViewport()
    renderProduct(NAME_50)

    const title = screen.getByRole('heading', { level: 3 })
    expect(title).toHaveTextContent(NAME_50)
    expect(title).not.toHaveTextContent('...')
    expect(title).toHaveAttribute('title', NAME_50)
  })
})
