import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import ImageUploadField from '@/pages/Upload/components/ImageUploadField'
import { setMobileViewport } from '@/test/utils/viewport'

const DESKTOP_HINT = '이 영역에 이미지 파일을 끌어다 놓거나, 영역을 클릭한 뒤 붙여넣을 수 있어요.'
const MOBILE_HINT = '탭해서 사진을 고를 수 있어요.'

const renderField = (onChange: (files: File[]) => void = () => {}) =>
  render(<ImageUploadField id="product-image" title="제품 대표 사진" description="제품을 구분할 대표 사진을 첨부하세요." onChange={onChange} />)

// 파일 입력은 화면에 보이지 않고(hidden) 라벨도 없어서 직접 찾는다.
const getFileInput = () => document.getElementById('product-image') as HTMLInputElement

// 끌어다 놓기·붙여넣기를 받는 영역: 키보드로 포커스할 수 있는(tabindex=0) 바깥 상자
const getDropArea = (hint: string) => screen.getByText(hint).closest('[tabindex="0"]') as HTMLElement

const imageFile = () => new File(['x'], 'photo.png', { type: 'image/png' })

const viewports = [
  { name: '데스크톱', prepare: () => {}, hint: DESKTOP_HINT },
  { name: '모바일', prepare: setMobileViewport, hint: MOBILE_HINT },
]

describe('이미지 업로드 영역 - 안내 문구', () => {
  it('데스크톱에서는 끌어다 놓거나 붙여넣을 수 있다고 안내한다', () => {
    renderField()

    expect(screen.getByText(DESKTOP_HINT)).toBeInTheDocument()
    expect(screen.queryByText(MOBILE_HINT)).not.toBeInTheDocument()
  })

  it('모바일에서는 탭해서 사진을 고를 수 있다고 안내한다', () => {
    setMobileViewport()
    renderField()

    expect(screen.getByText(MOBILE_HINT)).toBeInTheDocument()
    expect(screen.queryByText(DESKTOP_HINT)).not.toBeInTheDocument()
  })
})

describe('이미지 업로드 영역 - 파일 입력', () => {
  it.each(viewports)('$name에서도 이미지 파일만 받고 capture 속성은 두지 않는다', ({ prepare }) => {
    prepare()
    renderField()

    const input = getFileInput()
    expect(input).toHaveAttribute('accept', 'image/*')
    expect(input).not.toHaveAttribute('capture')
  })
})

// 좁은 데스크톱 창에서도 모바일 화면이 나오므로, 안내 문구와 상관없이 두 동작은 화면 폭에 관계없이 동작해야 한다.
describe('이미지 업로드 영역 - 끌어다 놓기와 붙여넣기', () => {
  it.each(viewports)('$name에서도 영역에 파일을 끌어다 놓으면 첨부된다', ({ prepare, hint }) => {
    prepare()
    const onChange = vi.fn()
    renderField(onChange)
    const file = imageFile()

    fireEvent.drop(getDropArea(hint), { dataTransfer: { files: [file] } })

    expect(onChange).toHaveBeenCalledWith([file])
  })

  it.each(viewports)('$name에서도 영역에 이미지를 붙여넣으면 첨부된다', ({ prepare, hint }) => {
    prepare()
    const onChange = vi.fn()
    renderField(onChange)
    const file = imageFile()

    fireEvent.paste(getDropArea(hint), { clipboardData: { files: [file] } })

    expect(onChange).toHaveBeenCalledWith([file])
  })
})
