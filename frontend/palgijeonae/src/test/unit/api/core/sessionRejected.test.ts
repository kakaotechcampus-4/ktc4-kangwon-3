import { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'

import { isSessionRejectedError } from '@/api/core/sessionRejected'

const responseError = (status: number) => new AxiosError('실패', undefined, undefined, undefined, { status } as never)

describe('isSessionRejectedError', () => {
  it.each([400, 401, 403, 404, 409])('%i 응답은 세션이 거절된 것으로 본다', (status) => {
    expect(isSessionRejectedError(responseError(status))).toBe(true)
  })

  it.each([429, 500, 502, 503])('%i 응답은 세션이 거절된 것으로 보지 않는다', (status) => {
    expect(isSessionRejectedError(responseError(status))).toBe(false)
  })

  it('응답이 없는 네트워크 오류와 타임아웃은 세션이 거절된 것으로 보지 않는다', () => {
    expect(isSessionRejectedError(new AxiosError('Network Error', AxiosError.ERR_NETWORK))).toBe(false)
    expect(isSessionRejectedError(new AxiosError('timeout', AxiosError.ETIMEDOUT))).toBe(false)
  })

  it('axios 오류가 아니면 세션이 거절된 것으로 보지 않는다', () => {
    expect(isSessionRejectedError(new Error('실패'))).toBe(false)
    expect(isSessionRejectedError(undefined)).toBe(false)
  })
})
