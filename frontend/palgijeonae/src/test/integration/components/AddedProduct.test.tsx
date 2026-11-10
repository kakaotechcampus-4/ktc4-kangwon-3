import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SourceType } from '@/api/types/common'
import AddedProduct from '@/pages/Upload/components/AddedProduct'
import { setMobileViewport } from '@/test/utils/viewport'

const TITLE = '블루투스 이어폰'

const renderProduct = (props: Partial<React.ComponentProps<typeof AddedProduct>> = {}) => {
  const handlers = { onOpenDetail: vi.fn(), onRemove: vi.fn() }
  render(<AddedProduct type={SourceType.Url} title={TITLE} {...handlers} {...props} />)
  return handlers
}

const getDetailButton = (title = TITLE) => screen.getByRole('button', { name: `${title} 자세히 보기` })

describe('추가된 상품 항목 - 표시', () => {
  it('제목과 입력 방식(URL)을 보여주고, 항목은 상세를 여는 버튼으로 알린다', () => {
    renderProduct()

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(TITLE)
    expect(screen.getByText('URL')).toBeInTheDocument()
    expect(getDetailButton()).toHaveAttribute('aria-haspopup', 'dialog')
  })

  it('글·이미지로 추가한 상품은 "이미지 / 텍스트"로 보여준다', () => {
    renderProduct({ type: SourceType.TextImage })

    expect(screen.getByText('이미지 / 텍스트')).toBeInTheDocument()
    expect(screen.queryByText('URL')).not.toBeInTheDocument()
  })

  // 한 줄 말줄임은 CSS(truncate)가 하므로, 글자를 자르지 않고 원본 제목을 그대로 두고 전체 제목을 title 속성으로 항상 제공한다.
  it.each([
    ['데스크톱', () => {}],
    ['모바일', setMobileViewport],
  ])('%s에서도 제목을 자르지 않고, 전체 제목을 title 속성으로 제공한다', (_name, prepare) => {
    prepare()
    const longTitle = '가'.repeat(60)
    renderProduct({ title: longTitle })

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(longTitle)
    expect(screen.getByRole('heading', { level: 3 })).not.toHaveTextContent('...')
    expect(getDetailButton(longTitle)).toHaveAttribute('title', longTitle)
  })

  it('짧은 제목도 title 속성으로 제공한다', () => {
    renderProduct()

    expect(getDetailButton()).toHaveAttribute('title', TITLE)
  })
})

describe('추가된 상품 항목 - 동작', () => {
  it('항목을 누르면 상세를 열고, 삭제는 부르지 않는다', async () => {
    const user = userEvent.setup()
    const { onOpenDetail, onRemove } = renderProduct()

    await user.click(getDetailButton())

    expect(onOpenDetail).toHaveBeenCalledTimes(1)
    expect(onRemove).not.toHaveBeenCalled()
  })

  it('키보드(Enter, Space)로도 상세를 연다', async () => {
    const user = userEvent.setup()
    const { onOpenDetail } = renderProduct()

    getDetailButton().focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    expect(onOpenDetail).toHaveBeenCalledTimes(2)
  })

  it('삭제를 누르면 삭제만 부르고, 항목 클릭(상세 열기)으로 전달되지 않는다', async () => {
    const user = userEvent.setup()
    const { onOpenDetail, onRemove } = renderProduct()

    await user.click(screen.getByRole('button', { name: '삭제' }))

    expect(onRemove).toHaveBeenCalledTimes(1)
    expect(onOpenDetail).not.toHaveBeenCalled()
  })
})
