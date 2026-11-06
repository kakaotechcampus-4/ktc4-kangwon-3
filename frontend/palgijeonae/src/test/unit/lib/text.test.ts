import { countGraphemes, truncateGraphemes, truncateToCodeUnitLength, truncateWithEllipsis } from '@/lib/text'

// .length는 코드 유닛 단위라 아래 문자들과 값이 다르다. 사용자가 보는 "글자 수"는 grapheme 기준이다.
const EMOJI = '😀' // 코드 유닛 2, grapheme 1
const FAMILY = '👨‍👩‍👧' // ZWJ로 이어 붙인 이모지: 코드 유닛 8, grapheme 1
const FLAG = '🇰🇷' // 국기(지역 표시 기호 2개): 코드 유닛 4, grapheme 1
const COMBINED_E = 'é' // e + 결합 악센트: 코드 유닛 2, grapheme 1
const DECOMPOSED_HAN = '한' // 한(NFD, 자모 분리): 코드 유닛 3, grapheme 1

describe('countGraphemes', () => {
  it('빈 문자열은 0이다', () => {
    expect(countGraphemes('')).toBe(0)
  })

  it('영문·숫자·한글은 글자 하나가 1이다', () => {
    expect(countGraphemes('abc123')).toBe(6)
    expect(countGraphemes('가나다')).toBe(3)
  })

  it('공백도 한 글자로 센다', () => {
    expect(countGraphemes('a b')).toBe(3)
  })

  it.each([
    ['이모지', EMOJI],
    ['ZWJ 가족 이모지', FAMILY],
    ['국기 이모지', FLAG],
    ['결합 문자(e + 악센트)', COMBINED_E],
    ['분해된 한글 자모', DECOMPOSED_HAN],
  ])('%s는 코드 유닛이 여러 개여도 1글자다', (_label, text) => {
    expect(text.length).toBeGreaterThan(1)
    expect(countGraphemes(text)).toBe(1)
  })

  it('여러 글자가 섞여 있어도 각각을 센다', () => {
    expect(countGraphemes(`a${EMOJI}${FAMILY}가${COMBINED_E}`)).toBe(5)
  })
})

describe('truncateGraphemes', () => {
  it('한도 이하면 원문을 그대로 돌려준다', () => {
    expect(truncateGraphemes('abc', 5)).toBe('abc')
    expect(truncateGraphemes('abc', 3)).toBe('abc')
  })

  it('한도를 넘으면 앞에서부터 한도만큼 자른다', () => {
    expect(truncateGraphemes('abcdef', 3)).toBe('abc')
    expect(truncateGraphemes('가나다라', 2)).toBe('가나')
  })

  it('이모지를 반으로 자르지 않는다', () => {
    expect(truncateGraphemes(`${EMOJI}${EMOJI}${EMOJI}`, 2)).toBe(`${EMOJI}${EMOJI}`)
    expect(truncateGraphemes(`${FAMILY}${FAMILY}`, 1)).toBe(FAMILY)
    expect(truncateGraphemes(`${FLAG}${FLAG}`, 1)).toBe(FLAG)
  })

  it('결합 문자를 기본 글자와 떼어놓지 않는다', () => {
    expect(truncateGraphemes(`${COMBINED_E}x${COMBINED_E}`, 1)).toBe(COMBINED_E)
  })

  it('한도가 0이면 빈 문자열이다', () => {
    expect(truncateGraphemes('abc', 0)).toBe('')
  })

  it('빈 문자열은 빈 문자열이다', () => {
    expect(truncateGraphemes('', 3)).toBe('')
  })
})

describe('truncateWithEllipsis', () => {
  it('한도 이하면 원문 그대로이고 말줄임표가 없다', () => {
    expect(truncateWithEllipsis('abc', 5)).toBe('abc')
  })

  it('정확히 한도와 같으면 말줄임표를 붙이지 않는다 (경계)', () => {
    expect(truncateWithEllipsis('abcde', 5)).toBe('abcde')
  })

  it('한도를 1글자라도 넘으면 자르고 ...를 붙인다 (경계)', () => {
    expect(truncateWithEllipsis('abcdef', 5)).toBe('abcde...')
  })

  it('한글도 글자 단위로 자른다', () => {
    expect(truncateWithEllipsis('블루투스 이어폰', 4)).toBe('블루투스...')
  })

  it('이모지는 한 글자로 세고 반으로 자르지 않는다', () => {
    expect(truncateWithEllipsis(`${EMOJI}${EMOJI}${EMOJI}`, 2)).toBe(`${EMOJI}${EMOJI}...`)
    expect(truncateWithEllipsis(`${FAMILY}${FAMILY}`, 2)).toBe(`${FAMILY}${FAMILY}`)
  })

  // 상품 카드·상품 미리보기가 제목을 보여줄 때 쓰는 한도(40자). 컴포넌트의 상수는 export되지 않아서 같은 값으로 확인한다.
  it('상품 제목 한도(40자): 40자는 그대로, 41자부터 40자 뒤에 ...를 붙인다', () => {
    expect(truncateWithEllipsis('가'.repeat(40), 40)).toBe('가'.repeat(40))
    expect(truncateWithEllipsis('가'.repeat(41), 40)).toBe(`${'가'.repeat(40)}...`)
    expect(truncateWithEllipsis('가'.repeat(100), 40)).toBe(`${'가'.repeat(40)}...`)
  })
})

describe('truncateToCodeUnitLength', () => {
  it('코드 유닛 길이가 한도 이하면 원문을 그대로 돌려준다', () => {
    expect(truncateToCodeUnitLength('abc', 3)).toBe('abc')
    expect(truncateToCodeUnitLength(EMOJI, 2)).toBe(EMOJI)
  })

  it('한도를 넘으면 한도 안에서 가능한 만큼만 채운다', () => {
    expect(truncateToCodeUnitLength('abcdef', 4)).toBe('abcd')
  })

  it('이모지가 코드 유닛 중간에서 잘리지 않는다 (서로게이트 쌍 보존)', () => {
    // 이모지 2개 = 코드 유닛 4. 한도 3이면 첫 이모지(2)만 담기고 둘째는 통째로 빠진다.
    expect(truncateToCodeUnitLength(`${EMOJI}${EMOJI}`, 3)).toBe(EMOJI)
  })

  it('한 글자(grapheme)가 한도를 넘으면 그 글자는 통째로 뺀다', () => {
    expect(FAMILY.length).toBe(8)
    expect(truncateToCodeUnitLength(FAMILY, 7)).toBe('')
    expect(truncateToCodeUnitLength(`a${FAMILY}`, 7)).toBe('a')
  })

  it('결과의 코드 유닛 길이는 한도를 넘지 않는다', () => {
    const text = `a${EMOJI}${FAMILY}${FLAG}가${COMBINED_E}`
    for (let max = 0; max <= text.length; max++) {
      expect(truncateToCodeUnitLength(text, max).length).toBeLessThanOrEqual(max)
    }
  })

  it('한도가 0이면 빈 문자열이다', () => {
    expect(truncateToCodeUnitLength('abc', 0)).toBe('')
  })

  it('빈 문자열은 빈 문자열이다', () => {
    expect(truncateToCodeUnitLength('', 5)).toBe('')
  })
})
