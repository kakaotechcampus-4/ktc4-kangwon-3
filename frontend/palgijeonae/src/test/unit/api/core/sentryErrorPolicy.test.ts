import { classifyApiError, toPathTemplate } from '@/api/core/sentryErrorPolicy'

describe('classifyApiError', () => {
  describe('BE 에러 코드를 우선 기준으로 판단한다', () => {
    it.each(['COMMON-001', 'COMMON-002', 'COMMON-007', 'AUTH-005'])('%s는 error', (code) => {
      expect(classifyApiError({ code, status: 400, retried: false })).toBe('error')
    })

    it.each(['FILE-001', 'FILE-003', 'COMMON-003', 'COMMON-005', 'COMMON-006', 'AUTH-004'])('%s는 warning', (code) => {
      expect(classifyApiError({ code, status: 400, retried: false })).toBe('warning')
    })

    it.each(['AUTH-001', 'AUTH-003', 'COMMON-009', 'COMMON-010', 'COMMON-011'])('%s는 보내지 않는다(null)', (code) => {
      expect(classifyApiError({ code, status: 400, retried: false })).toBeNull()
    })
  })

  describe('재시도 조건이 붙는 코드', () => {
    it.each(['AUTH-002', 'COMMON-004'])('%s: 최초 요청에서는 토큰 재발급으로 복구될 수 있어 보내지 않는다', (code) => {
      expect(classifyApiError({ code, status: 401, retried: false })).toBeNull()
    })

    it.each(['AUTH-002', 'COMMON-004'])('%s: 재발급 후 재시도한 요청에서 또 발생하면 warning', (code) => {
      expect(classifyApiError({ code, status: 401, retried: true })).toBe('warning')
    })
  })

  describe('코드가 상태코드보다 우선한다', () => {
    it('silent 코드는 500이어도 보내지 않는다', () => {
      expect(classifyApiError({ code: 'COMMON-011', status: 500, retried: false })).toBeNull()
    })

    it('error 코드는 4xx여도 error다', () => {
      expect(classifyApiError({ code: 'AUTH-005', status: 401, retried: false })).toBe('error')
    })

    it('warning 코드는 500이어도 warning이다', () => {
      expect(classifyApiError({ code: 'FILE-001', status: 500, retried: false })).toBe('warning')
    })

    it('silent 코드는 상태코드가 없어도 보내지 않는다', () => {
      expect(classifyApiError({ code: 'AUTH-001', retried: false })).toBeNull()
    })

    it('코드가 있는 error/warning 분류는 retried 값과 무관하다', () => {
      expect(classifyApiError({ code: 'COMMON-001', status: 400, retried: true })).toBe('error')
      expect(classifyApiError({ code: 'FILE-001', status: 400, retried: true })).toBe('warning')
    })
  })

  describe('코드가 없거나 알 수 없는 코드면 상태코드로 판단한다', () => {
    it.each([500, 502, 503])('코드 없이 상태코드 %i는 error', (status) => {
      expect(classifyApiError({ status, retried: false })).toBe('error')
    })

    it.each([400, 401, 403, 404, 429])('코드 없이 상태코드 %i는 보내지 않는다', (status) => {
      expect(classifyApiError({ status, retried: false })).toBeNull()
    })

    it('알 수 없는 코드는 상태코드 기준으로 판단한다', () => {
      expect(classifyApiError({ code: 'UNKNOWN-999', status: 500, retried: false })).toBe('error')
      expect(classifyApiError({ code: 'UNKNOWN-999', status: 404, retried: false })).toBeNull()
    })

    it('경계: 499는 보내지 않고 500부터 error다', () => {
      expect(classifyApiError({ status: 499, retried: false })).toBeNull()
      expect(classifyApiError({ status: 500, retried: false })).toBe('error')
    })

    it('빈 문자열 코드는 코드가 없는 것으로 보고 상태코드로 판단한다', () => {
      expect(classifyApiError({ code: '', status: 500, retried: false })).toBe('error')
      expect(classifyApiError({ code: '', status: 404, retried: false })).toBeNull()
    })
  })

  describe('응답 자체가 없는 경우(네트워크 오류 등)', () => {
    it('코드도 상태코드도 없으면 error다', () => {
      expect(classifyApiError({ retried: false })).toBe('error')
    })

    it('알 수 없는 코드이고 상태코드가 없으면 error다', () => {
      expect(classifyApiError({ code: 'UNKNOWN-999', retried: false })).toBe('error')
    })

    it('상태코드가 0이어도 응답이 없는 것으로 보고 error다', () => {
      expect(classifyApiError({ status: 0, retried: false })).toBe('error')
    })
  })
})

describe('toPathTemplate', () => {
  const UUID = '01a1a115-7a82-4b3c-9d1e-0123456789ab'
  const OTHER_UUID = 'ffffffff-0000-4000-8000-aaaaaaaaaaaa'

  describe('UUID 구간을 :id로 치환한다', () => {
    it('경로 중간의 UUID', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}/questions`)).toBe('/api/v1/diagnoses/:id/questions')
    })

    it('경로 끝의 UUID', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}`)).toBe('/api/v1/diagnoses/:id')
    })

    it('대문자 UUID도 치환한다', () => {
      expect(toPathTemplate(`/api/v1/products/${UUID.toUpperCase()}/retry`)).toBe('/api/v1/products/:id/retry')
    })

    it('UUID가 여러 개면 모두 치환한다', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}/products/${OTHER_UUID}`)).toBe('/api/v1/diagnoses/:id/products/:id')
    })

    it('id가 달라도 같은 엔드포인트는 같은 템플릿이 된다 (같은 이슈로 묶기 위함)', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}`)).toBe(toPathTemplate(`/api/v1/diagnoses/${OTHER_UUID}`))
    })

    it('호스트가 있는 절대 URL도 호스트는 두고 UUID만 치환한다', () => {
      expect(toPathTemplate(`https://api.example.com/api/v1/diagnoses/${UUID}`)).toBe('https://api.example.com/api/v1/diagnoses/:id')
    })
  })

  describe('쿼리스트링을 제거한다', () => {
    it('쿼리가 있으면 떼어낸다', () => {
      expect(toPathTemplate('/api/v1/products?page=0&size=10')).toBe('/api/v1/products')
    })

    it('쿼리 값에 UUID나 슬래시가 있어도 전부 제거한다', () => {
      expect(toPathTemplate(`/api/v1/products?redirect=/a/${UUID}`)).toBe('/api/v1/products')
    })

    it('UUID 뒤에 쿼리가 붙어도 치환 후 쿼리를 제거한다', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}?refresh=true`)).toBe('/api/v1/diagnoses/:id')
    })
  })

  describe('치환하지 않는 경우', () => {
    it('숫자만 있는 구간은 치환하지 않는다 (id는 UUID만 쓴다)', () => {
      expect(toPathTemplate('/api/v1/products/123')).toBe('/api/v1/products/123')
    })

    it('UUID 형태가 아닌 일반 구간은 그대로 둔다', () => {
      expect(toPathTemplate('/api/v1/auth/reissue')).toBe('/api/v1/auth/reissue')
    })

    it('길이나 형식이 UUID와 다르면 치환하지 않는다', () => {
      expect(toPathTemplate('/api/v1/products/01a1a115-7a82-4b3c-9d1e-0123456789')).toBe('/api/v1/products/01a1a115-7a82-4b3c-9d1e-0123456789')
      expect(toPathTemplate('/api/v1/products/zzzzzzzz-7a82-4b3c-9d1e-0123456789ab')).toBe('/api/v1/products/zzzzzzzz-7a82-4b3c-9d1e-0123456789ab')
    })

    it('구간의 일부로만 UUID가 들어 있으면 치환하지 않는다', () => {
      expect(toPathTemplate(`/api/v1/products/prefix-${UUID}`)).toBe(`/api/v1/products/prefix-${UUID}`)
      expect(toPathTemplate(`/api/v1/products/${UUID}-suffix`)).toBe(`/api/v1/products/${UUID}-suffix`)
    })
  })

  describe('경계', () => {
    it('빈 문자열은 빈 문자열이다 (config.url이 없을 때)', () => {
      expect(toPathTemplate('')).toBe('')
    })

    it('끝의 슬래시는 유지한다', () => {
      expect(toPathTemplate(`/api/v1/diagnoses/${UUID}/`)).toBe('/api/v1/diagnoses/:id/')
    })
  })
})
