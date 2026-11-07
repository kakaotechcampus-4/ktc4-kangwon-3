import { AxiosError, type AxiosResponse } from 'axios'

import { postDiagnosis, type PresignedFile, putToS3, requestPresignedUrls } from '@/api/diagnosis'
import { SourceType } from '@/api/types.ts'
import { buildDiagnosisPayload, submitDiagnosis, uploadProductImages } from '@/pages/Upload/diagnosisPipeline.ts'
import type { Product } from '@/pages/Upload/types.ts'

// 네트워크로 나가는 세 함수만 모킹한다. 에러 메시지를 만드는 getErrorMessage는 실제 구현을 쓴다.
vi.mock('@/api/diagnosis', () => ({
  requestPresignedUrls: vi.fn(),
  putToS3: vi.fn(),
  postDiagnosis: vi.fn(),
}))

const mockedRequestPresignedUrls = vi.mocked(requestPresignedUrls)
const mockedPutToS3 = vi.mocked(putToS3)
const mockedPostDiagnosis = vi.mocked(postDiagnosis)

const makeFile = (name: string, size = 100): File => {
  const file = new File(['a'], name, { type: 'image/png' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

// 요청한 파일 순서대로 key-0, key-1 ... 을 돌려주는 presigned 응답
const makePresigned = (count: number, prefix = 'key'): PresignedFile[] =>
  Array.from({ length: count }, (_, index) => ({
    fileName: `file-${index}`,
    key: `${prefix}-${index}`,
    presignedUrl: `https://s3.example.com/${prefix}-${index}`,
    contentType: `image/type-${index}`,
  }))

const makeUrlProduct = (overrides: Partial<Product> = {}): Product => ({
  id: '1',
  type: SourceType.Url,
  title: 'URL 상품',
  link: 'https://example.com/item',
  ...overrides,
})

const makeTextImageProduct = (overrides: Partial<Product> = {}): Product => ({
  id: '2',
  type: SourceType.TextImage,
  title: '텍스트 상품',
  content: '상세 내용',
  images: [],
  ...overrides,
})

// 서버가 { details: [{ message }] } 형태로 응답한 axios 에러
const makeAxiosError = (message: string): AxiosError => {
  const response = { status: 400, data: { details: [{ message }] }, headers: {}, statusText: '', config: {} } as AxiosResponse
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, response)
}

beforeEach(() => {
  vi.resetAllMocks()
  mockedPutToS3.mockResolvedValue({} as never)
})

describe('uploadProductImages', () => {
  it('업로드할 이미지가 없으면 API를 호출하지 않고 빈 결과를 돌려준다', async () => {
    const result = await uploadProductImages(makeUrlProduct())

    expect(result).toEqual({ productImageKey: undefined, imageKeys: [] })
    expect(mockedRequestPresignedUrls).not.toHaveBeenCalled()
    expect(mockedPutToS3).not.toHaveBeenCalled()
  })

  it('대표 이미지만 있으면 PRODUCT_MAIN 한 장을 요청하고 그 key를 productImageKey로 돌려준다', async () => {
    const main = makeFile('main.png', 300)
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(1))

    const result = await uploadProductImages(makeUrlProduct({ productImageFile: main }))

    expect(mockedRequestPresignedUrls).toHaveBeenCalledWith([{ type: 'PRODUCT_MAIN', fileName: 'main.png', fileSize: 300 }])
    expect(result).toEqual({ productImageKey: 'key-0', imageKeys: [] })
  })

  it('대표 이미지가 있으면 0번으로 요청하고, 나머지 상세 이미지는 PRODUCT_DETAIL로 이어서 요청한다', async () => {
    const main = makeFile('main.png', 1)
    const detailA = makeFile('a.png', 2)
    const detailB = makeFile('b.png', 3)
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(3))

    const result = await uploadProductImages(makeTextImageProduct({ productImageFile: main, images: [detailA, detailB] }))

    expect(mockedRequestPresignedUrls).toHaveBeenCalledWith([
      { type: 'PRODUCT_MAIN', fileName: 'main.png', fileSize: 1 },
      { type: 'PRODUCT_DETAIL', fileName: 'a.png', fileSize: 2 },
      { type: 'PRODUCT_DETAIL', fileName: 'b.png', fileSize: 3 },
    ])
    expect(result).toEqual({ productImageKey: 'key-0', imageKeys: ['key-1', 'key-2'] })
  })

  it('대표 이미지가 없으면 모든 이미지를 PRODUCT_DETAIL로 요청하고 productImageKey는 없다', async () => {
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(2))

    const result = await uploadProductImages(makeTextImageProduct({ images: [makeFile('a.png'), makeFile('b.png')] }))

    expect(mockedRequestPresignedUrls).toHaveBeenCalledWith([
      { type: 'PRODUCT_DETAIL', fileName: 'a.png', fileSize: 100 },
      { type: 'PRODUCT_DETAIL', fileName: 'b.png', fileSize: 100 },
    ])
    expect(result).toEqual({ productImageKey: undefined, imageKeys: ['key-0', 'key-1'] })
  })

  it('URL 입력은 images가 남아 있어도 상세 이미지를 올리지 않는다', async () => {
    const result = await uploadProductImages(makeUrlProduct({ images: [makeFile('ignored.png')] }))

    expect(result).toEqual({ productImageKey: undefined, imageKeys: [] })
    expect(mockedRequestPresignedUrls).not.toHaveBeenCalled()
  })

  it('발급받은 presigned URL을 요청과 같은 순서로 파일에 짝지어 S3에 올린다', async () => {
    const main = makeFile('main.png')
    const detail = makeFile('a.png')
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(2))

    await uploadProductImages(makeTextImageProduct({ productImageFile: main, images: [detail] }))

    expect(mockedPutToS3).toHaveBeenCalledTimes(2)
    expect(mockedPutToS3).toHaveBeenCalledWith('https://s3.example.com/key-0', main, 'image/type-0')
    expect(mockedPutToS3).toHaveBeenCalledWith('https://s3.example.com/key-1', detail, 'image/type-1')
  })

  it('발급받은 URL 개수가 요청한 파일 개수와 다르면 S3에 올리지 않고 실패한다', async () => {
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(1))

    await expect(uploadProductImages(makeTextImageProduct({ images: [makeFile('a.png'), makeFile('b.png')] }))).rejects.toThrow(
      '발급받은 presigned URL 개수가 요청한 파일 개수와 다릅니다.',
    )
    expect(mockedPutToS3).not.toHaveBeenCalled()
  })

  it('presigned URL 발급이 실패하면 그 에러로 실패한다', async () => {
    mockedRequestPresignedUrls.mockRejectedValue(new Error('발급 실패'))

    await expect(uploadProductImages(makeUrlProduct({ productImageFile: makeFile('main.png') }))).rejects.toThrow('발급 실패')
    expect(mockedPutToS3).not.toHaveBeenCalled()
  })

  it('S3 업로드가 하나라도 실패하면 실패한다', async () => {
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(2))
    mockedPutToS3.mockResolvedValueOnce({} as never).mockRejectedValueOnce(new Error('S3 실패'))

    await expect(uploadProductImages(makeTextImageProduct({ images: [makeFile('a.png'), makeFile('b.png')] }))).rejects.toThrow('S3 실패')
  })
})

describe('buildDiagnosisPayload', () => {
  it('URL 입력은 sourceUrl과 대표 이미지 key로 payload를 만든다', () => {
    const payload = buildDiagnosisPayload(makeUrlProduct({ title: '이어폰' }), { productImageKey: 'main-key', imageKeys: [] })

    expect(payload).toEqual({
      productName: '이어폰',
      productImageKey: 'main-key',
      sourceType: SourceType.Url,
      sourceUrl: 'https://example.com/item',
    })
  })

  it('URL 입력의 payload에는 텍스트·상세 이미지 필드가 없다', () => {
    const payload = buildDiagnosisPayload(makeUrlProduct(), { productImageKey: undefined, imageKeys: ['x'] })

    expect(payload).not.toHaveProperty('sourceText')
    expect(payload).not.toHaveProperty('imageKeys')
  })

  it('텍스트/이미지 입력은 sourceText와 상세 이미지 key들로 payload를 만든다', () => {
    const payload = buildDiagnosisPayload(makeTextImageProduct({ title: '의자', content: '의자 설명' }), {
      productImageKey: 'main-key',
      imageKeys: ['k1', 'k2'],
    })

    expect(payload).toEqual({
      productName: '의자',
      productImageKey: 'main-key',
      sourceType: SourceType.TextImage,
      sourceText: '의자 설명',
      imageKeys: ['k1', 'k2'],
    })
  })

  it('텍스트/이미지 입력의 payload에는 sourceUrl 필드가 없다', () => {
    const payload = buildDiagnosisPayload(makeTextImageProduct(), { productImageKey: undefined, imageKeys: [] })

    expect(payload).not.toHaveProperty('sourceUrl')
  })

  it('대표 이미지가 없으면 productImageKey는 undefined다', () => {
    const payload = buildDiagnosisPayload(makeUrlProduct(), { productImageKey: undefined, imageKeys: [] })

    expect(payload.productImageKey).toBeUndefined()
  })
})

describe('submitDiagnosis', () => {
  it('모든 상품을 업로드·조립한 뒤 한 번의 진단 요청으로 보내고 diagnosesId를 돌려준다', async () => {
    mockedPostDiagnosis.mockResolvedValue('diagnoses-1')

    const diagnosesId = await submitDiagnosis([makeUrlProduct({ title: 'A' }), makeTextImageProduct({ title: 'B', content: 'b' })])

    expect(diagnosesId).toBe('diagnoses-1')
    expect(mockedPostDiagnosis).toHaveBeenCalledTimes(1)
    expect(mockedPostDiagnosis).toHaveBeenCalledWith([
      { productName: 'A', productImageKey: undefined, sourceType: SourceType.Url, sourceUrl: 'https://example.com/item' },
      { productName: 'B', productImageKey: undefined, sourceType: SourceType.TextImage, sourceText: 'b', imageKeys: [] },
    ])
  })

  it('payload는 입력한 상품 순서를 유지한다', async () => {
    mockedPostDiagnosis.mockResolvedValue('id')

    await submitDiagnosis([makeUrlProduct({ title: '첫째' }), makeUrlProduct({ title: '둘째' }), makeUrlProduct({ title: '셋째' })])

    const sent = mockedPostDiagnosis.mock.calls[0][0]
    expect(sent.map((payload) => payload.productName)).toEqual(['첫째', '둘째', '셋째'])
  })

  it('이미지가 있는 상품은 업로드한 key를 payload에 담는다', async () => {
    mockedRequestPresignedUrls.mockResolvedValue(makePresigned(2))
    mockedPostDiagnosis.mockResolvedValue('id')

    await submitDiagnosis([makeTextImageProduct({ productImageFile: makeFile('main.png'), images: [makeFile('a.png')] })])

    expect(mockedPostDiagnosis.mock.calls[0][0][0]).toMatchObject({ productImageKey: 'key-0', imageKeys: ['key-1'] })
  })

  it('빈 배열이면 빈 payload로 진단 요청을 보낸다', async () => {
    mockedPostDiagnosis.mockResolvedValue('id')

    await submitDiagnosis([])

    expect(mockedPostDiagnosis).toHaveBeenCalledWith([])
  })

  describe('업로드 실패 처리', () => {
    it('실패한 상품이 있으면 진단 요청을 보내지 않고 상품 이름과 원인을 담아 실패한다', async () => {
      mockedRequestPresignedUrls.mockRejectedValue(new Error('S3 한도 초과'))

      await expect(submitDiagnosis([makeUrlProduct({ title: '고장난 상품', productImageFile: makeFile('main.png') })])).rejects.toThrow(
        '다음 상품의 진단 요청에 실패했습니다: 고장난 상품(S3 한도 초과)',
      )
      expect(mockedPostDiagnosis).not.toHaveBeenCalled()
    })

    it('성공한 상품과 실패한 상품이 섞여 있어도 실패한 상품만 알리고 진단 요청은 보내지 않는다', async () => {
      mockedRequestPresignedUrls.mockRejectedValue(new Error('실패'))

      await expect(
        submitDiagnosis([makeUrlProduct({ title: '성공 상품' }), makeUrlProduct({ title: '실패 상품', productImageFile: makeFile('main.png') })]),
      ).rejects.toThrow('다음 상품의 진단 요청에 실패했습니다: 실패 상품(실패)')
      expect(mockedPostDiagnosis).not.toHaveBeenCalled()
    })

    it('실패한 상품이 여러 개면 모두 쉼표로 이어서 알린다', async () => {
      mockedRequestPresignedUrls.mockRejectedValueOnce(new Error('원인1')).mockRejectedValueOnce(new Error('원인2'))

      await expect(
        submitDiagnosis([
          makeUrlProduct({ title: 'A', productImageFile: makeFile('a.png') }),
          makeUrlProduct({ title: 'B', productImageFile: makeFile('b.png') }),
        ]),
      ).rejects.toThrow('다음 상품의 진단 요청에 실패했습니다: A(원인1), B(원인2)')
    })

    it('서버 에러 응답이면 details의 메시지를 원인으로 쓴다', async () => {
      mockedRequestPresignedUrls.mockRejectedValue(makeAxiosError('허용되지 않는 파일입니다.'))

      await expect(submitDiagnosis([makeUrlProduct({ title: 'A', productImageFile: makeFile('a.png') })])).rejects.toThrow(
        '다음 상품의 진단 요청에 실패했습니다: A(허용되지 않는 파일입니다.)',
      )
    })

    it('Error가 아닌 값으로 실패하면 기본 메시지를 원인으로 쓴다', async () => {
      mockedRequestPresignedUrls.mockRejectedValue('문자열로 던진 실패')

      await expect(submitDiagnosis([makeUrlProduct({ title: 'A', productImageFile: makeFile('a.png') })])).rejects.toThrow(
        '다음 상품의 진단 요청에 실패했습니다: A(이미지 업로드에 실패했습니다.)',
      )
    })

    it('presigned URL 개수가 맞지 않는 것도 해당 상품의 실패로 알린다', async () => {
      mockedRequestPresignedUrls.mockResolvedValue([])

      await expect(submitDiagnosis([makeUrlProduct({ title: 'A', productImageFile: makeFile('a.png') })])).rejects.toThrow(
        '다음 상품의 진단 요청에 실패했습니다: A(발급받은 presigned URL 개수가 요청한 파일 개수와 다릅니다.)',
      )
    })
  })

  it('진단 요청(postDiagnosis) 자체가 실패하면 그 에러를 그대로 전달한다', async () => {
    mockedPostDiagnosis.mockRejectedValue(new Error('진단 요청 실패'))

    await expect(submitDiagnosis([makeUrlProduct()])).rejects.toThrow('진단 요청 실패')
  })
})
