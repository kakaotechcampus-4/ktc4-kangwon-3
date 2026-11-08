import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ProductTabs from '@/components/common/ProductTabs'
import { setMobileViewport } from '@/test/utils/viewport'

const LONG_NAME = '가나다라마바사아자차카타'

describe('ProductTabs - 말줄임', () => {
  it('데스크톱에서는 상품명을 10글자까지 보여주고 넘으면 ...를 붙이며, 전체 이름을 title 속성으로 남긴다', () => {
    render(<ProductTabs productNames={[LONG_NAME]} selected={0} onSelect={() => {}} />)

    const tab = screen.getByRole('tab', { name: '가나다라마바사아자차...' })
    expect(tab).toHaveAttribute('title', LONG_NAME)
  })

  it('데스크톱에서 자르지 않은 이름에는 title 속성을 달지 않는다', () => {
    render(<ProductTabs productNames={['가나다라마바사아자차']} selected={0} onSelect={() => {}} />)

    expect(screen.getByRole('tab', { name: '가나다라마바사아자차' })).not.toHaveAttribute('title')
  })

  it('모바일에서는 글자 수로 자르지 않고 원본 이름을 넘기며(CSS가 한 줄로 자름), 전체 이름을 title 속성으로 남긴다', () => {
    setMobileViewport()
    render(<ProductTabs productNames={[LONG_NAME]} selected={0} onSelect={() => {}} />)

    const tab = screen.getByRole('tab', { name: LONG_NAME })
    expect(tab).toHaveTextContent(LONG_NAME)
    expect(tab).not.toHaveTextContent('...')
    expect(tab).toHaveAttribute('title', LONG_NAME)
  })
})
