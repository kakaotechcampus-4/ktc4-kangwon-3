import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import defaultThumbnail from '@/assets/upload-defaultThumbnail.svg'
import AttachedImages from '@/pages/Result/components/ProductInfo/components/AttachedImages'

const PRODUCT_NAME = '무선 이어폰'
const IMAGE_URLS = ['https://example.com/1.png', 'https://example.com/2.png', 'https://example.com/3.png']

const renderImages = (imageUrls = IMAGE_URLS) => render(<AttachedImages productName={PRODUCT_NAME} imageUrls={imageUrls} />)

const thumbnailButton = (number: number) => screen.getByRole('button', { name: `${PRODUCT_NAME} 상세 이미지 ${number} 크게 보기` })
const getLightbox = () => screen.queryByRole('dialog', { name: '이미지 미리보기' })
const lightboxImageSrc = (number: number) =>
  within(getLightbox() as HTMLElement).getAllByRole('img', { name: `${PRODUCT_NAME} 상세 이미지 ${number}` })[0].getAttribute('src')

describe('첨부된 이미지', () => {
  it('첨부한 이미지가 없으면 아무것도 보여주지 않는다', () => {
    renderImages([])

    expect(screen.queryByText('첨부된 이미지')).not.toBeInTheDocument()
  })

  it('첨부한 이미지마다 번호가 붙은 썸네일 버튼을 보여준다', () => {
    renderImages()

    expect(screen.getByText('첨부된 이미지')).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(IMAGE_URLS.length)
    expect(thumbnailButton(2)).toHaveTextContent('상세 이미지 2')
  })

  it('썸네일을 누르면 그 이미지를 크게 보여주고, 넘기면 다른 이미지를, 닫으면 확대 창을 없앤다', async () => {
    const user = userEvent.setup()
    renderImages()
    expect(getLightbox()).not.toBeInTheDocument()

    await user.click(thumbnailButton(2))

    expect(lightboxImageSrc(2)).toBe(IMAGE_URLS[1])

    await user.click(screen.getByRole('button', { name: '다음 이미지' }))

    expect(lightboxImageSrc(3)).toBe(IMAGE_URLS[2])

    await user.keyboard('{Escape}')

    expect(getLightbox()).not.toBeInTheDocument()
  })

  it('이미지를 불러오지 못하면 기본 썸네일로 바꾼다', () => {
    renderImages()
    const image = thumbnailButton(1).querySelector('img') as HTMLImageElement

    fireEvent.error(image)

    expect(image.getAttribute('src')).toBe(defaultThumbnail)
  })
})
