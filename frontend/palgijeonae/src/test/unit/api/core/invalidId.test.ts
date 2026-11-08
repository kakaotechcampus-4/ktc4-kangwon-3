import { AxiosError } from 'axios'

import { isInvalidIdError } from '@/api/core/invalidId'

const responseError = (status: number) => new AxiosError('실패', undefined, undefined, undefined, { status } as never)

describe('isInvalidIdError', () => {
  it.each([400, 404])('%i 응답은 유효하지 않은 id로 본다', (status) => {
    expect(isInvalidIdError(responseError(status))).toBe(true)
  })

  it.each([401, 403, 409, 429, 500, 503])('%i 응답은 유효하지 않은 id로 보지 않는다', (status) => {
    expect(isInvalidIdError(responseError(status))).toBe(false)
  })

  it('응답이 없는 네트워크 오류는 유효하지 않은 id로 보지 않는다', () => {
    expect(isInvalidIdError(new AxiosError('Network Error', AxiosError.ERR_NETWORK))).toBe(false)
  })

  it('axios 오류가 아니거나 오류가 없으면 유효하지 않은 id로 보지 않는다', () => {
    expect(isInvalidIdError(new Error('실패'))).toBe(false)
    expect(isInvalidIdError(null)).toBe(false)
  })
})
