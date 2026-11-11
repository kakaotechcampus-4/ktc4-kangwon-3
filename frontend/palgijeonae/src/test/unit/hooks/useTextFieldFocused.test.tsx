import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useTextFieldFocused } from '@/hooks/useTextFieldFocused'

const fields: HTMLElement[] = []
const addElement = (tag: 'textarea' | 'input' | 'button') => {
  const element = document.createElement(tag)
  document.body.appendChild(element)
  fields.push(element)
  return element
}

afterEach(() => {
  fields.splice(0).forEach((element) => element.remove())
})

describe('useTextFieldFocused', () => {
  it('아무 칸에도 포커스가 없으면 false이다', () => {
    const { result } = renderHook(() => useTextFieldFocused())

    expect(result.current).toBe(false)
  })

  it('textarea나 input에 포커스가 가면 true이고, 포커스를 잃으면 false이다', () => {
    const textarea = addElement('textarea')
    const input = addElement('input')
    const { result } = renderHook(() => useTextFieldFocused())

    act(() => textarea.focus())
    expect(result.current).toBe(true)

    act(() => textarea.blur())
    expect(result.current).toBe(false)

    act(() => input.focus())
    expect(result.current).toBe(true)
  })

  it('버튼처럼 글자를 입력하지 않는 요소에 포커스가 가면 false이다', () => {
    const textarea = addElement('textarea')
    const button = addElement('button')
    const { result } = renderHook(() => useTextFieldFocused())

    act(() => textarea.focus())
    act(() => button.focus())

    expect(result.current).toBe(false)
  })

  it('처음부터 입력칸에 포커스가 있으면 true로 시작한다', () => {
    addElement('textarea').focus()

    expect(renderHook(() => useTextFieldFocused()).result.current).toBe(true)
  })
})
