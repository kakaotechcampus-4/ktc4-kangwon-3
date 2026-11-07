import { AxiosError } from 'axios'

import { getRetryDelay, shouldRetryQuery } from '@/api/queryRetry'

const responseError = (status: number, headers: Record<string, string> = {}) =>
  new AxiosError('실패', undefined, undefined, undefined, { status, headers } as never)

describe('shouldRetryQuery', () => {
  it.each([400, 401, 403, 404, 409, 499])('%i 응답은 재시도하지 않는다', (status) => {
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

  describe('429 (요청 한도 초과)', () => {
    it('Retry-After가 있으면 재시도한다', () => {
      expect(shouldRetryQuery(0, responseError(429, { 'retry-after': '1' }))).toBe(true)
    })

    it.each<Record<string, string>>([{}, { 'retry-after': '0' }, { 'retry-after': 'abc' }])('Retry-After가 없거나 올바르지 않으면 재시도하지 않는다 (%o)', (headers) => {
      expect(shouldRetryQuery(0, responseError(429, headers))).toBe(false)
    })

    it('재시도는 최대 3회까지다', () => {
      expect(shouldRetryQuery(2, responseError(429, { 'retry-after': '1' }))).toBe(true)
      expect(shouldRetryQuery(3, responseError(429, { 'retry-after': '1' }))).toBe(false)
    })
  })
})

describe('getRetryDelay', () => {
  it('429는 Retry-After(초)만큼 기다린다', () => {
    expect(getRetryDelay(0, responseError(429, { 'retry-after': '3' }))).toBe(3000)
  })

  it('그 외에는 1초, 2초, 4초로 늘려 가며 기다리고 30초를 넘기지 않는다', () => {
    expect(getRetryDelay(0, responseError(503))).toBe(1000)
    expect(getRetryDelay(1, responseError(503))).toBe(2000)
    expect(getRetryDelay(2, responseError(503))).toBe(4000)
    expect(getRetryDelay(10, responseError(503))).toBe(30_000)
  })

  it('Retry-After가 없는 429도 기본 대기 시간을 쓴다', () => {
    expect(getRetryDelay(1, responseError(429))).toBe(2000)
  })
})
