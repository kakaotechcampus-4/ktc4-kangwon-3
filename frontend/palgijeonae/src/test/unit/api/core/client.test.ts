import axios, { AxiosError } from 'axios'
import { delay, http } from 'msw'

import { API_URL, S3_URL } from '@/test/mocks/handlers'
import { errorResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'

const TIMEOUT_MESSAGE = '응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.'
// NOTE(source): 타임아웃 값이 export되지 않아 소스(client.ts, diagnosis.ts)의 값과 같게 직접 둔다.
const API_TIMEOUT_MS = 10_000
const S3_UPLOAD_TIMEOUT_MS = 60_000

// 응답이 오지 않는 서버를 흉내 낸다.
const hangUp = () => delay('infinite')

// 모듈 상태(진행 중인 재발급 Promise)가 테스트 사이에 새지 않도록, 매번 모듈을 새로 불러온다.
let apiClient: typeof import('@/api/core/client').default
let getErrorMessage: typeof import('@/api/core/client').getErrorMessage
let reissueAccessToken: typeof import('@/api/core/client').reissueAccessToken
let putToS3: typeof import('@/api/uploads').putToS3

beforeEach(async () => {
  vi.resetModules()
  ;({ default: apiClient, getErrorMessage, reissueAccessToken } = await import('@/api/core/client'))
  ;({ putToS3 } = await import('@/api/uploads'))
})

// 가짜 타이머로 시간을 앞당겨, 실제로 기다리지 않고 타임아웃을 일으킨다.
async function waitForError(request: Promise<unknown>, ms: number): Promise<AxiosError> {
  const settled = request.then(
    () => {
      throw new Error('타임아웃 없이 응답이 왔습니다.')
    },
    (error: AxiosError) => error,
  )
  await vi.advanceTimersByTimeAsync(ms)
  return settled
}

describe('요청 타임아웃', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('일반 API', () => {
    it('응답이 오지 않으면 10초 뒤 요청을 끊고, 사용자에게 보여줄 안내 문구를 돌려준다', async () => {
      server.use(http.get(`${API_URL}/api/v1/products/:productId`, hangUp))

      const error = await waitForError(apiClient.get('/api/v1/products/product-1'), API_TIMEOUT_MS)

      expect(error.response).toBeUndefined()
      expect(getErrorMessage(error, '기본 메시지')).toBe(TIMEOUT_MESSAGE)
    })

    it('10초가 지나기 전에 온 응답은 끊지 않고 그대로 처리한다', async () => {
      server.use(
        http.get(`${API_URL}/api/v1/products/:productId`, async () => {
          await delay(9_000)
          return errorResponse(404)
        }),
      )

      const error = await waitForError(apiClient.get('/api/v1/products/product-1'), 9_000)

      expect(error.response?.status).toBe(404)
    })
  })

  describe('토큰 재발급', () => {
    it('응답이 오지 않으면 10초 뒤 끊고, 이후 다시 호출하면 새 요청을 보낸다', async () => {
      server.use(http.post(`${API_URL}/api/v1/auth/reissue`, hangUp))

      const error = await waitForError(reissueAccessToken(), API_TIMEOUT_MS)
      expect(getErrorMessage(error, '기본 메시지')).toBe(TIMEOUT_MESSAGE)

      server.use(http.post(`${API_URL}/api/v1/auth/reissue`, () => Response.json({ data: { accessToken: 'new-token' } })))
      await expect(reissueAccessToken()).resolves.toBeDefined()
    })
  })

  describe('S3 업로드', () => {
    it('일반 API(10초)보다 오래 기다리고, 60초 뒤 끊는다', async () => {
      server.use(http.put(`${S3_URL}/*`, hangUp))
      const file = new File(['image-bytes'], 'a.png', { type: 'image/png' })
      let outcome: AxiosError | 'pending' = 'pending'
      putToS3(`${S3_URL}/uploads/0-a.png`, file, 'image/png').catch((error: AxiosError) => {
        outcome = error
      })

      await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS)
      expect(outcome).toBe('pending')

      await vi.advanceTimersByTimeAsync(S3_UPLOAD_TIMEOUT_MS - API_TIMEOUT_MS)
      expect(axios.isAxiosError(outcome)).toBe(true)
      expect(getErrorMessage(outcome, '기본 메시지')).toBe(TIMEOUT_MESSAGE)
    })
  })
})

describe('getErrorMessage: 타임아웃 판별', () => {
  it('요청이 중단된 오류(timeout 문구 없음)는 타임아웃 안내로 바꾸지 않는다', () => {
    const aborted = new AxiosError('Request aborted', AxiosError.ECONNABORTED)

    expect(getErrorMessage(aborted, '기본 메시지')).toBe('기본 메시지')
  })

  it('ETIMEDOUT도 타임아웃으로 본다', () => {
    const timedOut = new AxiosError('timeout of 10000ms exceeded', AxiosError.ETIMEDOUT)

    expect(getErrorMessage(timedOut, '기본 메시지')).toBe(TIMEOUT_MESSAGE)
  })

  it('서버가 응답한 오류는 타임아웃 안내로 바꾸지 않는다', () => {
    const error = new AxiosError('timeout of 10000ms exceeded', AxiosError.ECONNABORTED, undefined, undefined, {
      status: 500,
      data: { code: 'COMMON-001', message: '서버 오류' },
    } as never)

    expect(getErrorMessage(error, '기본 메시지')).toBe('서버 오류')
  })
})
