import { isHttpUrl } from '@/lib/url'

describe('isHttpUrl', () => {
  describe('http(s) URL은 통과한다', () => {
    it.each([
      'https://example.com',
      'http://example.com',
      'https://detail.1688.com/offer/739214086512.html',
      'https://www.google.com/search?q=%ED%8C%8C%EC%9D%BC&udm=2#sv=CAMS',
      'http://localhost:5173/path',
    ])('%s', (url) => {
      expect(isHttpUrl(url)).toBe(true)
    })

    it('스킴의 대소문자는 구분하지 않는다', () => {
      expect(isHttpUrl('HTTPS://example.com')).toBe(true)
      expect(isHttpUrl('Http://example.com')).toBe(true)
    })
  })

  describe('다른 스킴은 막는다', () => {
    it.each([
      'javascript:alert(1)',
      'JAVASCRIPT:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'ftp://example.com',
      'mailto:a@example.com',
      'file:///etc/passwd',
    ])('%s', (url) => {
      expect(isHttpUrl(url)).toBe(false)
    })
  })

  describe('앱 내부 경로·상대 경로는 막는다', () => {
    it.each([
      '/mypage',
      '/judgement/abc',
      '//evil.com',
      './mypage',
      '../mypage',
      'abc',
      'www.example.com',
      'example.com',
    ])('%s', (url) => {
      expect(isHttpUrl(url)).toBe(false)
    })
  })

  describe('불완전한 입력', () => {
    it('빈 문자열은 막는다', () => {
      expect(isHttpUrl('')).toBe(false)
    })

    it.each(['https:/example.com', 'https:example.com', 'http//example.com', 'https', 'http:'])(
      '스킴 구분자(://)가 온전하지 않으면 막는다: %s',
      (url) => {
        expect(isHttpUrl(url)).toBe(false)
      },
    )

    // 스킴 접두사만 검사하는 것이 현재 기준이다. 호스트가 유효한지는 판단하지 않는다.
    it('접두사만 검사하므로 `https://`만 있어도 통과한다 (호스트 유효성은 보지 않는다)', () => {
      expect(isHttpUrl('https://')).toBe(true)
    })
  })

  describe('공백 처리', () => {
    // 앞쪽 공백은 trim하지 않는다. 호출하는 쪽에서 trim한 값을 넘겨야 한다. (InputForm은 link.trim()으로 저장)
    it('앞쪽 공백이 있으면 막는다', () => {
      expect(isHttpUrl(' https://example.com')).toBe(false)
      expect(isHttpUrl('\nhttps://example.com')).toBe(false)
    })

    it('뒤쪽 공백은 접두사 검사에 영향이 없어 통과한다', () => {
      expect(isHttpUrl('https://example.com ')).toBe(true)
    })

    it('제로폭 문자가 앞에 붙으면 막는다', () => {
      expect(isHttpUrl('​https://example.com')).toBe(false)
    })
  })
})
