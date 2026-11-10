import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SourceType } from '@/api/types/common'
import ProductDetailModal from '@/pages/Upload/components/ProductDetailModal'
import type { Product } from '@/pages/Upload/types'

const makeFile = (name: string) => new File(['image-bytes'], name, { type: 'image/png' })

const urlProduct = (overrides: Partial<Product> = {}): Product => ({
  id: 'p1',
  type: SourceType.Url,
  title: '블루투스 이어폰',
  link: 'https://example.com/item',
  ...overrides,
})

// 컴포넌트가 files가 바뀔 때마다 미리보기 주소를 다시 만들므로, 렌더 사이에 같은 배열을 쓴다.
const IMAGES = [makeFile('a.png'), makeFile('b.png'), makeFile('c.png')]

const textImageProduct = (overrides: Partial<Product> = {}): Product => ({
  id: 'p2',
  type: SourceType.TextImage,
  title: '캠핑 테이블',
  content: '접이식 알루미늄 테이블입니다.',
  images: IMAGES,
  ...overrides,
})

const renderModal = (product: Product, props: Partial<React.ComponentProps<typeof ProductDetailModal>> = {}) => {
  const handlers = { onClose: vi.fn(), onRemove: vi.fn(), onImageClick: vi.fn() }
  render(<ProductDetailModal product={product} {...handlers} {...props} />)
  return handlers
}

const getDialog = (title: string) => screen.getByRole('dialog', { name: title })

describe('상품 자세히 보기 모달 - URL 상품', () => {
  it('제목과 입력 방식을 보여주고, 링크를 새 탭으로 열리는 a 태그로 보여준다', () => {
    renderModal(urlProduct())
    const dialog = getDialog('블루투스 이어폰')

    expect(within(dialog).getByRole('heading', { level: 2, name: '블루투스 이어폰' })).toBeInTheDocument()
    expect(within(dialog).getByText('URL')).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: '링크' })).toBeInTheDocument()
    const link = within(dialog).getByRole('link', { name: 'https://example.com/item' })
    expect(link).toHaveAttribute('href', 'https://example.com/item')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('http(s)로 시작하지 않는 링크는 눌러 이동하지 않도록 글자로만 보여준다', () => {
    renderModal(urlProduct({ link: 'javascript:alert(1)' }))

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
  })

  it('내용과 상세페이지 이미지 영역은 보여주지 않는다', () => {
    renderModal(urlProduct())

    expect(screen.queryByRole('heading', { name: '내용' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '상세페이지 이미지' })).not.toBeInTheDocument()
  })
})

describe('상품 자세히 보기 모달 - 이미지·텍스트 상품', () => {
  it('입력 방식을 "이미지 / 텍스트"로, 내용과 상세페이지 이미지 썸네일을 보여준다', () => {
    renderModal(textImageProduct())
    const dialog = getDialog('캠핑 테이블')

    expect(within(dialog).getByText('이미지 / 텍스트')).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: '내용' })).toBeInTheDocument()
    expect(within(dialog).getByText('접이식 알루미늄 테이블입니다.')).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: '상세페이지 이미지' })).toBeInTheDocument()
    expect(within(dialog).getAllByRole('button', { name: /크게 보기$/ })).toHaveLength(IMAGES.length)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('내용이 없으면 내용 영역을, 이미지가 없으면 이미지 영역을 보여주지 않는다', () => {
    renderModal(textImageProduct({ content: undefined, images: [] }))

    expect(screen.queryByRole('heading', { name: '내용' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '상세페이지 이미지' })).not.toBeInTheDocument()
  })

  it('썸네일을 누르면 확대 창을 직접 띄우지 않고 누른 순번을 알린다', async () => {
    const user = userEvent.setup()
    const { onImageClick } = renderModal(textImageProduct())

    await user.click(screen.getByRole('button', { name: 'b.png 크게 보기' }))

    expect(onImageClick).toHaveBeenCalledTimes(1)
    expect(onImageClick).toHaveBeenCalledWith(1)
    expect(screen.queryByRole('dialog', { name: '이미지 미리보기' })).not.toBeInTheDocument()
  })

  it('focusImageIndex를 주면 그 순번의 썸네일에 포커스를 둔다', () => {
    renderModal(textImageProduct(), { focusImageIndex: 2 })

    expect(screen.getByRole('button', { name: 'c.png 크게 보기' })).toHaveFocus()
  })
})

describe('상품 자세히 보기 모달 - 대표 사진과 버튼', () => {
  it('대표 사진이 있으면 그 사진을 썸네일로 쓴다', () => {
    renderModal(urlProduct({ productImageFile: makeFile('main.png') }))

    expect(within(getDialog('블루투스 이어폰')).getByAltText('상품 썸네일')).toHaveAttribute('src', 'blob:mock-object-url')
  })

  it('"목록에서 삭제"는 삭제를, 아래 "닫기"와 위 닫기 버튼은 닫기를 알린다', async () => {
    const user = userEvent.setup()
    const { onClose, onRemove } = renderModal(urlProduct())

    await user.click(screen.getByRole('button', { name: '목록에서 삭제' }))
    expect(onRemove).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '닫기' }))
    expect(onClose).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: '창 닫기' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
