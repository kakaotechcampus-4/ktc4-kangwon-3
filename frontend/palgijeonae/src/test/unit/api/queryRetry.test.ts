import { AxiosError } from 'axios'

import { shouldRetryQuery } from '@/api/queryRetry'

const responseError = (status: number) => new AxiosError('실패', undefined, undefined, undefined, { status } as never)

describe('shouldRetryQuery', () => {
  it.each([400, 401, 403, 404, 409, 429, 499])('%i 응답은 재시도하지 않는다', (status) => {
    expect(shouldRetryQuery(0, responseError(status))).toBe(false)
  })

  it.each([500, 502, 503])('%i 응답은 최대 3회까지 재시도한다', (status) => {
    expect(shouldRetryQuery(0, responseError(status))).toBe(true)
    expect(shouldRetryQuery(2, responseError(status))).toBe(true)
    expect(shouldRetryQuery(3, responseError(status))).toBe(false)
  })

  it('응답이 없는 네트워크 오류는 최대 3회까지 재시도한다', () => {
    const networkError = new AxiosError('Network Error', AxiosError.ERR_NETWORK)

    expect(shouldRetryQuery(0, networkError)).toBe(true)
    expect(shouldRetryQuery(3, networkError)).toBe(false)
  })

  it('axios 오류가 아니면 최대 3회까지 재시도한다', () => {
    expect(shouldRetryQuery(0, new Error('알 수 없는 오류'))).toBe(true)
    expect(shouldRetryQuery(3, new Error('알 수 없는 오류'))).toBe(false)
  })
})
