import { render, renderHook, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import PreviewFrame from '@/components/common/PreviewFrame'
import { usePreviewScale } from '@/components/common/PreviewFrame/usePreviewScale'
import { setMobileViewport } from '@/test/utils/viewport'

// jsdom에는 ResizeObserver가 없다. 크기 변화 감지는 이 테스트의 관심사가 아니라서 아무것도 하지 않는 스텁을 쓴다.
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
})
afterEach(() => {
  vi.unstubAllGlobals()
})

const getInner = () => screen.getByLabelText('미리보기').firstElementChild as HTMLElement
const getFigure = () => screen.getByLabelText('미리보기')

describe('PreviewFrame - 펼치는 폭', () => {
  it('데스크톱에서는 baseWidth로 펼친다', () => {
    render(<PreviewFrame label="미리보기" baseWidth={1000}>내용</PreviewFrame>)

    expect(getInner().style.width).toBe('1000px')
  })

  it('모바일에서는 mobileBaseWidth로 펼치고, 주지 않으면 모바일 본문 폭(350px)을 쓴다', () => {
    setMobileViewport()
    render(<PreviewFrame label="미리보기" baseWidth={1000}>내용</PreviewFrame>)

    expect(getInner().style.width).toBe('350px')
  })

  it('모바일에서 mobileBaseWidth를 주면 그 값으로 펼친다', () => {
    setMobileViewport()
    render(<PreviewFrame label="미리보기" baseWidth={1000} mobileBaseWidth={320}>내용</PreviewFrame>)

    expect(getInner().style.width).toBe('320px')
  })
})

describe('PreviewFrame - 최대 높이', () => {
  it('데스크톱에서는 maxHeight를 쓴다', () => {
    render(<PreviewFrame label="미리보기" baseWidth={1000} maxHeight={520} mobileMaxHeight={440}>내용</PreviewFrame>)

    expect(getFigure().style.maxHeight).toBe('520px')
  })

  it('모바일에서는 mobileMaxHeight를 쓴다', () => {
    setMobileViewport()
    render(<PreviewFrame label="미리보기" baseWidth={1000} maxHeight={520} mobileMaxHeight={440}>내용</PreviewFrame>)

    expect(getFigure().style.maxHeight).toBe('440px')
  })

  it('모바일에서 mobileMaxHeight가 없으면 maxHeight를 그대로 쓴다', () => {
    setMobileViewport()
    render(<PreviewFrame label="미리보기" baseWidth={1000} maxHeight={520}>내용</PreviewFrame>)

    expect(getFigure().style.maxHeight).toBe('520px')
  })

  it('높이 제한이 없으면 maxHeight 스타일도 달지 않는다', () => {
    setMobileViewport()
    render(<PreviewFrame label="미리보기" baseWidth={1000}>내용</PreviewFrame>)

    expect(getFigure().style.maxHeight).toBe('')
  })
})

describe('usePreviewScale - baseWidth 전환', () => {
  const buildRef = (width: number) => {
    const element = document.createElement('div')
    element.getBoundingClientRect = () => ({ width }) as DOMRect
    return { current: element }
  }

  it('담긴 공간 너비를 baseWidth로 나눈 비율로 줄인다', () => {
    const { result } = renderHook(() => usePreviewScale(buildRef(250), 1000))

    expect(result.current).toBe(0.25)
  })

  it('baseWidth가 바뀌면 비율도 다시 계산한다 (데스크톱 기준 폭에서 모바일 기준 폭으로)', () => {
    const ref = buildRef(250)
    const { result, rerender } = renderHook(({ baseWidth }) => usePreviewScale(ref, baseWidth), { initialProps: { baseWidth: 1000 } })
    expect(result.current).toBe(0.25)

    rerender({ baseWidth: 350 })

    expect(result.current).toBeCloseTo(250 / 350)
  })

  it('확대는 하지 않는다(최대 1)', () => {
    const { result } = renderHook(() => usePreviewScale(buildRef(500), 350))

    expect(result.current).toBe(1)
  })
})
