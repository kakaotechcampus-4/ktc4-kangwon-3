import { isMissingRouteParam } from '@/lib/routeParams'

describe('isMissingRouteParam', () => {
  describe('누락으로 판단한다', () => {
    it('undefined', () => {
      expect(isMissingRouteParam(undefined)).toBe(true)
    })

    it('빈 문자열', () => {
      expect(isMissingRouteParam('')).toBe(true)
    })

    it.each(['undefined', 'null'])('문자열 그대로 들어온 "%s"', (value) => {
      expect(isMissingRouteParam(value)).toBe(true)
    })
  })

  describe('정상 값으로 판단한다', () => {
    it.each([
      '01a1a115-7a82-4b3c-9d1e-0123456789ab',
      '123',
      '0',
      'abc',
    ])('%s', (value) => {
      expect(isMissingRouteParam(value)).toBe(false)
    })
  })

  describe('경계: 정확히 일치하는 경우만 누락이다', () => {
    it('대소문자가 다르면 정상 값이다', () => {
      expect(isMissingRouteParam('Undefined')).toBe(false)
      expect(isMissingRouteParam('NULL')).toBe(false)
    })

    it('공백이 섞이면 정상 값이다 (trim하지 않는다)', () => {
      expect(isMissingRouteParam(' ')).toBe(false)
      expect(isMissingRouteParam(' undefined')).toBe(false)
    })

    it('다른 문자열의 일부로 들어간 경우는 정상 값이다', () => {
      expect(isMissingRouteParam('null-id')).toBe(false)
      expect(isMissingRouteParam('undefined1')).toBe(false)
    })
  })
})
