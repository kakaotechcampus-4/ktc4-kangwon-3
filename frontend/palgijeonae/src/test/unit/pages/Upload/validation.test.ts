import { SourceType } from '@/api/types.ts'
import { MAX_FILE_SIZE_BYTES, MAX_PRODUCT_IMAGE_COUNT, MAX_PRODUCT_NAME_CODE_UNIT_LENGTH, MAX_PRODUCT_NAME_LENGTH } from '@/pages/Upload/constraints.ts'
import type { Product } from '@/pages/Upload/types.ts'
import { isAllowedImageType, isWithinFileSizeLimit, validateImageFile, validateProduct } from '@/pages/Upload/validation.ts'

const FAMILY = '👨‍👩‍👧' // grapheme 1, 코드 유닛 8

// 실제 용량만큼 메모리를 쓰지 않도록 size만 덮어쓴 File을 만든다.
const makeImage = ({ type = 'image/png', size = 1024, name = 'a.png' }: { type?: string; size?: number; name?: string } = {}): File => {
  const file = new File(['a'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

const makeUrlProduct = (overrides: Partial<Product> = {}): Product => ({
  id: '1',
  type: SourceType.Url,
  title: '테스트 상품',
  link: 'https://example.com/item',
  ...overrides,
})

const makeTextImageProduct = (overrides: Partial<Product> = {}): Product => ({
  id: '1',
  type: SourceType.TextImage,
  title: '테스트 상품',
  content: '상세페이지 내용',
  images: [],
  ...overrides,
})

const TYPE_ERROR = 'jpeg, jpg, png, webp 형식의 이미지만 첨부할 수 있습니다.'
const SIZE_ERROR = '이미지는 1장당 10MB까지만 첨부할 수 있습니다.'

describe('isAllowedImageType', () => {
  it.each(['image/jpeg', 'image/jpg', 'image/png', 'image/webp'])('%s는 허용한다', (type) => {
    expect(isAllowedImageType(makeImage({ type }))).toBe(true)
  })

  it.each(['image/gif', 'image/svg+xml', 'application/pdf', 'text/plain', ''])('"%s"는 허용하지 않는다', (type) => {
    expect(isAllowedImageType(makeImage({ type }))).toBe(false)
  })
})

describe('isWithinFileSizeLimit', () => {
  it('한도(10MB)와 정확히 같으면 허용한다 (경계)', () => {
    expect(isWithinFileSizeLimit(makeImage({ size: MAX_FILE_SIZE_BYTES }))).toBe(true)
  })

  it('한도보다 1바이트라도 크면 허용하지 않는다 (경계)', () => {
    expect(isWithinFileSizeLimit(makeImage({ size: MAX_FILE_SIZE_BYTES + 1 }))).toBe(false)
  })

  it('작은 파일과 빈 파일은 허용한다', () => {
    expect(isWithinFileSizeLimit(makeImage({ size: 1 }))).toBe(true)
    expect(isWithinFileSizeLimit(makeImage({ size: 0 }))).toBe(true)
  })
})

describe('validateImageFile', () => {
  it('허용된 형식이고 크기가 한도 이내면 null이다', () => {
    expect(validateImageFile(makeImage())).toBeNull()
  })

  it('형식이 허용되지 않으면 형식 오류를 돌려준다', () => {
    expect(validateImageFile(makeImage({ type: 'image/gif' }))).toBe(TYPE_ERROR)
  })

  it('크기가 한도를 넘으면 크기 오류를 돌려준다', () => {
    expect(validateImageFile(makeImage({ size: MAX_FILE_SIZE_BYTES + 1 }))).toBe(SIZE_ERROR)
  })

  it('형식과 크기가 모두 잘못되면 형식 오류를 먼저 돌려준다', () => {
    expect(validateImageFile(makeImage({ type: 'image/gif', size: MAX_FILE_SIZE_BYTES + 1 }))).toBe(TYPE_ERROR)
  })
})

describe('validateProduct', () => {
  describe('상품명', () => {
    it.each(['', '   ', '\n\t'])('비어 있거나 공백뿐이면 오류다: %j', (title) => {
      expect(validateProduct(makeUrlProduct({ title }))).toBe('제품명을 입력해주세요.')
    })

    it(`${MAX_PRODUCT_NAME_LENGTH}자(보이는 글자 수)는 통과한다 (경계)`, () => {
      expect(validateProduct(makeUrlProduct({ title: 'a'.repeat(MAX_PRODUCT_NAME_LENGTH) }))).toBeNull()
    })

    it(`${MAX_PRODUCT_NAME_LENGTH + 1}자는 글자 수 오류다 (경계)`, () => {
      expect(validateProduct(makeUrlProduct({ title: 'a'.repeat(MAX_PRODUCT_NAME_LENGTH + 1) }))).toBe(
        `제품명은 ${MAX_PRODUCT_NAME_LENGTH}자를 넘을 수 없습니다.`,
      )
    })

    it('이모지는 코드 유닛이 아니라 글자 단위로 센다', () => {
      // 😀 100개 = 100글자, 코드 유닛 200 → 두 한도 모두 경계에서 통과한다.
      expect(validateProduct(makeUrlProduct({ title: '😀'.repeat(MAX_PRODUCT_NAME_LENGTH) }))).toBeNull()
    })

    it(`글자 수는 한도 이내여도 코드 유닛이 ${MAX_PRODUCT_NAME_CODE_UNIT_LENGTH}를 넘으면 이모지 오류다`, () => {
      const title = FAMILY.repeat(26) // 26글자, 코드 유닛 208
      expect(title.length).toBeGreaterThan(MAX_PRODUCT_NAME_CODE_UNIT_LENGTH)
      expect(validateProduct(makeUrlProduct({ title }))).toBe('이모지를 너무 많이 사용했습니다. 이모지 개수를 줄여주세요.')
    })

    it('코드 유닛이 한도와 정확히 같으면 통과한다 (경계)', () => {
      const title = FAMILY.repeat(25) // 25글자, 코드 유닛 200
      expect(title.length).toBe(MAX_PRODUCT_NAME_CODE_UNIT_LENGTH)
      expect(validateProduct(makeUrlProduct({ title }))).toBeNull()
    })

    it('글자 수 오류와 이모지 오류가 모두 해당되면 글자 수 오류를 먼저 돌려준다', () => {
      expect(validateProduct(makeUrlProduct({ title: '😀'.repeat(MAX_PRODUCT_NAME_LENGTH + 1) }))).toBe(
        `제품명은 ${MAX_PRODUCT_NAME_LENGTH}자를 넘을 수 없습니다.`,
      )
    })
  })

  describe('대표 이미지(썸네일)', () => {
    it('없어도 통과한다', () => {
      expect(validateProduct(makeUrlProduct({ productImageFile: undefined }))).toBeNull()
    })

    it('허용된 이미지면 통과한다', () => {
      expect(validateProduct(makeUrlProduct({ productImageFile: makeImage() }))).toBeNull()
    })

    it('형식이 허용되지 않으면 오류다', () => {
      expect(validateProduct(makeUrlProduct({ productImageFile: makeImage({ type: 'image/gif' }) }))).toBe(TYPE_ERROR)
    })

    it('크기가 한도를 넘으면 오류다', () => {
      expect(validateProduct(makeUrlProduct({ productImageFile: makeImage({ size: MAX_FILE_SIZE_BYTES + 1 }) }))).toBe(SIZE_ERROR)
    })

    it('링크 검증보다 먼저 확인한다', () => {
      const product = makeUrlProduct({ link: '', productImageFile: makeImage({ type: 'image/gif' }) })
      expect(validateProduct(product)).toBe(TYPE_ERROR)
    })
  })

  describe('URL 입력', () => {
    it('http(s) 링크면 통과한다', () => {
      expect(validateProduct(makeUrlProduct({ link: 'https://example.com' }))).toBeNull()
      expect(validateProduct(makeUrlProduct({ link: 'http://example.com' }))).toBeNull()
    })

    it.each([undefined, '', '   '])('링크가 없거나 공백뿐이면 오류다: %j', (link) => {
      expect(validateProduct(makeUrlProduct({ link }))).toBe('상세페이지 링크를 입력해주세요.')
    })

    it.each(['abc', 'www.example.com', '/mypage', 'javascript:alert(1)', 'ftp://example.com'])(
      'http(s)로 시작하지 않으면 오류다: %s',
      (link) => {
        expect(validateProduct(makeUrlProduct({ link }))).toBe('상세페이지 링크는 http:// 또는 https://로 시작해야 합니다.')
      },
    )

    // 회귀: URL 입력은 content·images를 쓰지 않는다. 링크 검증을 통과하면 content 검사로 넘어가지 않고 끝나야 한다.
    it('내용·이미지 없이 올바른 링크만 있어도 통과한다', () => {
      const product = makeUrlProduct({ content: undefined, images: undefined })
      expect(validateProduct(product)).toBeNull()
    })

    it('URL 입력에서는 상세 이미지가 잘못돼도 검사하지 않는다', () => {
      const product = makeUrlProduct({ images: [makeImage({ type: 'image/gif' })] })
      expect(validateProduct(product)).toBeNull()
    })
  })

  describe('텍스트/이미지 입력: 내용', () => {
    it('내용이 있으면 통과한다', () => {
      expect(validateProduct(makeTextImageProduct())).toBeNull()
    })

    it.each([undefined, '', '   ', '\n'])('내용이 없거나 공백뿐이면 오류다: %j', (content) => {
      expect(validateProduct(makeTextImageProduct({ content }))).toBe('상세페이지 내용을 입력해주세요.')
    })

    it('이미지가 있어도 텍스트 없이는 제출할 수 없다 (이미지는 보조 입력)', () => {
      const product = makeTextImageProduct({ content: '', images: [makeImage()] })
      expect(validateProduct(product)).toBe('상세페이지 내용을 입력해주세요.')
    })

    it('텍스트 입력에서는 링크가 없어도 된다', () => {
      expect(validateProduct(makeTextImageProduct({ link: undefined }))).toBeNull()
    })
  })

  describe('텍스트/이미지 입력: 상세 이미지', () => {
    it('이미지가 없어도(undefined) 통과한다', () => {
      expect(validateProduct(makeTextImageProduct({ images: undefined }))).toBeNull()
    })

    it(`${MAX_PRODUCT_IMAGE_COUNT}장은 통과한다 (경계)`, () => {
      const images = Array.from({ length: MAX_PRODUCT_IMAGE_COUNT }, () => makeImage())
      expect(validateProduct(makeTextImageProduct({ images }))).toBeNull()
    })

    it(`${MAX_PRODUCT_IMAGE_COUNT + 1}장은 개수 오류다 (경계)`, () => {
      const images = Array.from({ length: MAX_PRODUCT_IMAGE_COUNT + 1 }, () => makeImage())
      expect(validateProduct(makeTextImageProduct({ images }))).toBe(`이미지는 최대 ${MAX_PRODUCT_IMAGE_COUNT}장까지 첨부할 수 있습니다.`)
    })

    it('형식이 허용되지 않는 이미지가 있으면 오류다', () => {
      const images = [makeImage(), makeImage({ type: 'image/gif' })]
      expect(validateProduct(makeTextImageProduct({ images }))).toBe(TYPE_ERROR)
    })

    it('크기가 한도를 넘는 이미지가 있으면 오류다', () => {
      const images = [makeImage(), makeImage({ size: MAX_FILE_SIZE_BYTES + 1 })]
      expect(validateProduct(makeTextImageProduct({ images }))).toBe(SIZE_ERROR)
    })

    it('잘못된 이미지가 여러 개면 첫 번째 오류를 돌려준다', () => {
      const images = [makeImage({ size: MAX_FILE_SIZE_BYTES + 1 }), makeImage({ type: 'image/gif' })]
      expect(validateProduct(makeTextImageProduct({ images }))).toBe(SIZE_ERROR)
    })

    it('개수 초과는 개별 이미지 검사보다 먼저 확인한다', () => {
      const images = Array.from({ length: MAX_PRODUCT_IMAGE_COUNT + 1 }, () => makeImage({ type: 'image/gif' }))
      expect(validateProduct(makeTextImageProduct({ images }))).toBe(`이미지는 최대 ${MAX_PRODUCT_IMAGE_COUNT}장까지 첨부할 수 있습니다.`)
    })
  })
})
