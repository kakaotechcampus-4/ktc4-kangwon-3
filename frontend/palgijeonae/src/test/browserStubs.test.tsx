import { render, screen } from '@testing-library/react'

import { SourceType } from '@/api/types/common.ts'
import AddedProduct from '@/pages/Upload/components/AddedProduct'

// vitest.setup.ts의 브라우저 API 스텁이 의도대로 동작하는지 확인한다.
describe('브라우저 API 스텁', () => {
  it('URL.createObjectURL은 고정된 가짜 주소를 반환하고 호출을 기록한다', () => {
    const file = new File(['a'], 'a.png', { type: 'image/png' })

    expect(URL.createObjectURL(file)).toBe('blob:mock-object-url')
    expect(URL.createObjectURL).toHaveBeenCalledWith(file)
  })

  it('스텁 호출 기록은 테스트마다 초기화된다', () => {
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  })

  it('상품 썸네일은 파일로 만든 주소를 쓰고, 화면이 사라지면 그 주소를 해제한다', () => {
    const file = new File(['a'], 'thumb.png', { type: 'image/png' })
    const { unmount } = render(
      <AddedProduct type={SourceType.Url} title="테스트 상품" productImageFile={file} onOpenDetail={() => {}} onRemove={() => {}} />,
    )

    expect(URL.createObjectURL).toHaveBeenCalledWith(file)
    expect(screen.getByAltText('상품 썸네일')).toHaveAttribute('src', 'blob:mock-object-url')

    unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-object-url')
  })

  it('FormData는 기본 구현을 그대로 쓴다', () => {
    const formData = new FormData()
    const file = new File(['a'], 'a.png', { type: 'image/png' })
    formData.append('file', file)

    expect(formData.get('file')).toBeInstanceOf(File)
  })
})
