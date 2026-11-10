import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SourceType } from '@/api/types/common'
import AddedProductPanel from '@/pages/Upload/components/AddedProductPanel'
import type { Product } from '@/pages/Upload/types'
import { UPLOAD_MESSAGES } from '@/test/constants/messages'

const makeProduct = (index: number, overrides: Partial<Product> = {}): Product => ({
  id: `product-${index}`,
  type: SourceType.Url,
  title: `상품 ${index}`,
  link: 'https://example.com/item',
  ...overrides,
})

const renderPanel = (products: Product[]) => {
  const handlers = { onOpenDetail: vi.fn(), onRemove: vi.fn() }
  render(<AddedProductPanel products={products} {...handlers} />)
  return handlers
}

const getList = () => screen.getByRole('list', { name: '확인할 제품 목록' })

describe('확인할 제품 패널 - 표시', () => {
  it('상품이 없어도 패널을 보여주고, 목록 대신 빈 상태 안내를 보여준다', () => {
    renderPanel([])

    expect(screen.getByRole('heading', { name: '확인할 제품' })).toBeInTheDocument()
    expect(screen.getByText(UPLOAD_MESSAGES.PANEL_EMPTY)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: '확인할 제품 목록' })).not.toBeInTheDocument()
    expect(screen.queryByText('항목을 누르면 입력 내용을 자세히 볼 수 있어요.')).not.toBeInTheDocument()
  })

  it('상품이 있으면 빈 상태 안내를 보여주지 않는다', () => {
    renderPanel([makeProduct(1)])

    expect(screen.queryByText(UPLOAD_MESSAGES.PANEL_EMPTY)).not.toBeInTheDocument()
  })

  it('제목, 추가한 순서대로의 항목 목록, 안내 문구를 보여준다', () => {
    renderPanel([makeProduct(1), makeProduct(2, { type: SourceType.TextImage }), makeProduct(3)])

    expect(screen.getByRole('heading', { name: '확인할 제품' })).toBeInTheDocument()
    const items = within(getList()).getAllByRole('listitem')
    expect(items.map((item) => within(item).getByRole('heading').textContent)).toEqual(['상품 1', '상품 2', '상품 3'])
    expect(screen.getByText('항목을 누르면 입력 내용을 자세히 볼 수 있어요.')).toBeInTheDocument()
  })

  it('개수 표시와 진단 시작 버튼은 패널 안에 두지 않는다', () => {
    renderPanel([makeProduct(1), makeProduct(2)])

    expect(screen.queryByText(/\d+\s*\/\s*10/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /진단 시작하기/ })).not.toBeInTheDocument()
  })
})

describe('확인할 제품 패널 - 동작', () => {
  it('항목을 누르면 그 상품의 id로 상세 열기를 알린다', async () => {
    const user = userEvent.setup()
    const { onOpenDetail, onRemove } = renderPanel([makeProduct(1), makeProduct(2)])

    await user.click(screen.getByRole('button', { name: '상품 2 자세히 보기' }))

    expect(onOpenDetail).toHaveBeenCalledTimes(1)
    expect(onOpenDetail).toHaveBeenCalledWith('product-2')
    expect(onRemove).not.toHaveBeenCalled()
  })

  it('삭제를 누르면 그 상품의 id로 삭제를 알리고, 상세는 열지 않는다', async () => {
    const user = userEvent.setup()
    const { onOpenDetail, onRemove } = renderPanel([makeProduct(1), makeProduct(2)])
    const secondItem = within(getList()).getAllByRole('listitem')[1]

    await user.click(within(secondItem).getByRole('button', { name: '삭제' }))

    expect(onRemove).toHaveBeenCalledTimes(1)
    expect(onRemove).toHaveBeenCalledWith('product-2')
    expect(onOpenDetail).not.toHaveBeenCalled()
  })
})
