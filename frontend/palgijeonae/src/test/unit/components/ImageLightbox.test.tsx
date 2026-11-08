import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ImageLightbox, { type LightboxImage } from '@/components/common/ImageLightbox'

const IMAGES: LightboxImage[] = [
  { src: 'https://example.com/1.png', alt: '이미지 1' },
  { src: 'https://example.com/2.png', alt: '이미지 2' },
  { src: 'https://example.com/3.png', alt: '이미지 3' },
]

// 뒤 화면을 막는 inert는 앱의 #root에 걸리므로, 테스트에서도 같은 요소를 만들어 둔다.
let appRoot: HTMLDivElement

beforeEach(() => {
  appRoot = document.createElement('div')
  appRoot.id = 'root'
  document.body.appendChild(appRoot)
})

afterEach(() => {
  appRoot.remove()
})

const renderLightbox = (props: Partial<React.ComponentProps<typeof ImageLightbox>> = {}) => {
  const handlers = { onIndexChange: vi.fn(), onClose: vi.fn() }
  const view = render(<ImageLightbox images={IMAGES} currentIndex={0} {...handlers} {...props} />)
  return { ...view, ...handlers }
}

const getDialog = () => screen.getByRole('dialog', { name: '이미지 미리보기' })

describe('ImageLightbox - 표시', () => {
  it('현재 이미지를 대화상자로 보여주고, 열리면 대화상자로 포커스를 옮긴다', () => {
    renderLightbox({ currentIndex: 1 })

    expect(getDialog()).toHaveAttribute('aria-modal', 'true')
    expect(within(getDialog()).getAllByRole('img', { name: '이미지 2' })[0]).toHaveAttribute('src', IMAGES[1].src)
    expect(getDialog()).toHaveFocus()
  })

  it('이미지가 여러 장이면 이전·다음 버튼과 썸네일을 보여주고, 현재 썸네일에 aria-current를 둔다', () => {
    renderLightbox({ currentIndex: 1 })

    expect(screen.getByRole('button', { name: '이전 이미지' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다음 이미지' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '이미지 2' })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('button', { name: '이미지 1' })).not.toHaveAttribute('aria-current')
  })

  it('이미지가 한 장이면 이전·다음 버튼과 썸네일을 보여주지 않는다', () => {
    renderLightbox({ images: [IMAGES[0]] })

    expect(screen.queryByRole('button', { name: '이전 이미지' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다음 이미지' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '이미지 1' })).not.toBeInTheDocument()
  })

  it('보여줄 이미지가 없으면 아무것도 그리지 않는다', () => {
    renderLightbox({ images: [], currentIndex: 0 })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('ImageLightbox - 이미지 넘기기', () => {
  it('다음 버튼은 다음 순번을, 마지막에서는 처음 순번을 알린다', async () => {
    const user = userEvent.setup()
    const first = renderLightbox({ currentIndex: 0 })
    await user.click(screen.getByRole('button', { name: '다음 이미지' }))
    expect(first.onIndexChange).toHaveBeenLastCalledWith(1)
    first.unmount()

    const last = renderLightbox({ currentIndex: 2 })
    await user.click(screen.getByRole('button', { name: '다음 이미지' }))
    expect(last.onIndexChange).toHaveBeenLastCalledWith(0)
  })

  it('이전 버튼은 이전 순번을, 처음에서는 마지막 순번을 알린다', async () => {
    const user = userEvent.setup()
    const middle = renderLightbox({ currentIndex: 1 })
    await user.click(screen.getByRole('button', { name: '이전 이미지' }))
    expect(middle.onIndexChange).toHaveBeenLastCalledWith(0)
    middle.unmount()

    const first = renderLightbox({ currentIndex: 0 })
    await user.click(screen.getByRole('button', { name: '이전 이미지' }))
    expect(first.onIndexChange).toHaveBeenLastCalledWith(2)
  })

  it('썸네일을 누르면 그 순번을 알린다', async () => {
    const user = userEvent.setup()
    const { onIndexChange } = renderLightbox({ currentIndex: 0 })

    await user.click(screen.getByRole('button', { name: '이미지 3' }))

    expect(onIndexChange).toHaveBeenCalledWith(2)
  })

  it('방향키로 이전·다음 이미지로 넘기고, Esc로 닫는다', async () => {
    const user = userEvent.setup()
    const { onIndexChange, onClose } = renderLightbox({ currentIndex: 1 })

    await user.keyboard('{ArrowRight}')
    expect(onIndexChange).toHaveBeenLastCalledWith(2)

    await user.keyboard('{ArrowLeft}')
    expect(onIndexChange).toHaveBeenLastCalledWith(0)

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('ImageLightbox - 닫기와 삭제', () => {
  it('닫기 버튼과 바깥 배경을 누르면 닫지만, 이미지 영역을 눌러서는 닫지 않는다', async () => {
    const user = userEvent.setup()
    const { onClose } = renderLightbox()

    await user.click(within(getDialog()).getAllByRole('img', { name: '이미지 1' })[0])
    expect(onClose).not.toHaveBeenCalled()

    // 닫기 버튼의 클릭은 배경까지 전달돼 onClose가 두 번 불릴 수 있어, 횟수가 아니라 호출 여부만 본다.
    await user.click(screen.getByRole('button', { name: '닫기' }))
    expect(onClose).toHaveBeenCalled()

    onClose.mockClear()
    await user.click(getDialog())
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('onRemove가 있으면 삭제 버튼이 현재 순번을 알리고, 없으면 삭제 버튼을 보여주지 않는다', async () => {
    const user = userEvent.setup()
    const onRemove = vi.fn()
    const withRemove = renderLightbox({ currentIndex: 1, onRemove })

    await user.click(screen.getByRole('button', { name: '삭제' }))
    expect(onRemove).toHaveBeenCalledWith(1)
    withRemove.unmount()

    renderLightbox({ currentIndex: 1 })
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})

describe('ImageLightbox - 뒤 화면 막기', () => {
  it('열려 있는 동안 배경 스크롤과 뒤 화면 접근을 막고, 닫으면 풀고 원래 포커스로 돌려준다', () => {
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()

    const { unmount } = renderLightbox()

    expect(document.body.style.overflow).toBe('hidden')
    expect(appRoot.inert).toBe(true)

    unmount()

    expect(document.body.style.overflow).toBe('')
    expect(appRoot.inert).toBe(false)
    expect(opener).toHaveFocus()
    opener.remove()
  })
})
