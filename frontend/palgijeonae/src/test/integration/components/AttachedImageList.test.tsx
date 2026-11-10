import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import AttachedImageList from '@/pages/Upload/components/AttachedImageList'

const makeFile = (name: string) => new File(['image-bytes'], name, { type: 'image/png' })

// 컴포넌트가 files가 바뀔 때마다 미리보기 주소를 다시 만들므로, 렌더 사이에 같은 배열을 쓴다.
const FILES = [makeFile('a.png'), makeFile('b.png'), makeFile('c.png')]

const thumbnail = (name: string) => screen.getByRole('button', { name: `${name} 크게 보기` })
const getLightbox = () => screen.queryByRole('dialog', { name: '이미지 미리보기' })

describe('첨부 이미지 목록 - 썸네일 클릭', () => {
  it('기본에서는 썸네일을 누르면 이 목록이 확대 창을 띄운다', async () => {
    const user = userEvent.setup()
    render(<AttachedImageList title="이미지" files={FILES} />)

    await user.click(thumbnail('b.png'))

    expect(getLightbox()).toBeInTheDocument()
  })

  it('onImageClick을 넘기면 확대 창을 띄우지 않고 누른 순번만 알린다', async () => {
    const user = userEvent.setup()
    const onImageClick = vi.fn()
    render(<AttachedImageList title="이미지" files={FILES} onImageClick={onImageClick} />)

    await user.click(thumbnail('c.png'))

    expect(onImageClick).toHaveBeenCalledTimes(1)
    expect(onImageClick).toHaveBeenCalledWith(2)
    expect(getLightbox()).not.toBeInTheDocument()
  })
})

describe('첨부 이미지 목록 - 포커스', () => {
  it('focusIndex를 주면 그 순번의 썸네일에 처음부터 포커스를 둔다', () => {
    render(<AttachedImageList title="이미지" files={FILES} focusIndex={1} />)

    expect(thumbnail('b.png')).toHaveFocus()
  })

  it('focusIndex를 주지 않으면 포커스를 옮기지 않는다', () => {
    render(<AttachedImageList title="이미지" files={FILES} />)

    expect(document.body).toHaveFocus()
  })
})
