import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SourceType } from '@/api/types/common'
import UploadActionBar from '@/pages/Upload/components/UploadActionBar'
import type { Product } from '@/pages/Upload/types'

const makeProduct = (index: number, overrides: Partial<Product> = {}): Product => ({
  id: `product-${index}`,
  type: SourceType.Url,
  title: `상품 ${index}`,
  link: 'https://example.com/item',
  ...overrides,
})

const makeProducts = (count: number) => Array.from({ length: count }, (_, index) => makeProduct(index + 1))

const renderBar = (products: Product[]) => {
  const handlers = { onStart: vi.fn(), onShowList: vi.fn() }
  const view = render(<UploadActionBar products={products} {...handlers} />)
  return { ...view, ...handlers }
}

describe('업로드 하단 바 - 표시', () => {
  it('담은 상품 수를 "n / 10"으로 보여준다', () => {
    renderBar(makeProducts(3))

    expect(screen.getByText('3 / 10')).toBeInTheDocument()
  })

  it('상품이 없어도 "0 / 10"과 진단 시작하기 버튼을 보여주고, 목록 보기 버튼은 보여주지 않는다', () => {
    renderBar([])

    expect(screen.getByText('0 / 10')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '진단 시작하기' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '목록 보기' })).not.toBeInTheDocument()
  })

  it('상품이 있으면 목록 보기 버튼을 보여준다', () => {
    renderBar(makeProducts(1))

    expect(screen.getByRole('button', { name: '목록 보기' })).toBeInTheDocument()
  })

  it('상품 썸네일은 최대 3개까지만 겹쳐 보여준다', () => {
    const { container } = renderBar(makeProducts(5))

    // 썸네일은 장식이라 대체 텍스트가 없다. 바 안의 이미지 수로 센다.
    expect(container.querySelectorAll('img')).toHaveLength(3)
  })

  it('상품이 3개 미만이면 그만큼만 보여준다', () => {
    const { container } = renderBar(makeProducts(2))

    expect(container.querySelectorAll('img')).toHaveLength(2)
  })

  it('대표 사진이 있는 상품은 그 사진을 썸네일로 쓴다', () => {
    const file = new File(['a'], 'main.png', { type: 'image/png' })
    const { container } = renderBar([makeProduct(1, { productImageFile: file })])

    expect(URL.createObjectURL).toHaveBeenCalledWith(file)
    expect(container.querySelector('img')).toHaveAttribute('src', 'blob:mock-object-url')
  })
})

describe('업로드 하단 바 - 동작', () => {
  it('진단 시작하기를 누르면 시작을 알린다', async () => {
    const user = userEvent.setup()
    const { onStart, onShowList } = renderBar(makeProducts(2))

    await user.click(screen.getByRole('button', { name: '진단 시작하기' }))

    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onShowList).not.toHaveBeenCalled()
  })

  it('목록 보기를 누르면 목록으로 이동을 알린다', async () => {
    const user = userEvent.setup()
    const { onStart, onShowList } = renderBar(makeProducts(2))

    await user.click(screen.getByRole('button', { name: '목록 보기' }))

    expect(onShowList).toHaveBeenCalledTimes(1)
    expect(onStart).not.toHaveBeenCalled()
  })
})

describe('업로드 하단 바 - 페이지 아래 여백', () => {
  it('떠 있는 동안 Layout이 읽는 아래 여백 값을 정하고, 사라지면 지운다', () => {
    const { unmount } = renderBar(makeProducts(1))
    expect(document.documentElement.style.getPropertyValue('--action-bar-space')).not.toBe('')

    unmount()

    expect(document.documentElement.style.getPropertyValue('--action-bar-space')).toBe('')
  })
})
