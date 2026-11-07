import axios from 'axios'
import { http } from 'msw'

import { getErrorMessage } from '@/api/core/client'
import { postDiagnosis } from '@/api/diagnoses'
import { getProduct, submitAnswers } from '@/api/products'
import { ProcessingStatusType, SourceType } from '@/api/types/common'
import { putToS3, requestPresignedUrls } from '@/api/uploads'
import type { Product } from '@/pages/Upload/types'
import { submitDiagnosis } from '@/pages/Upload/utils/diagnosisPipeline'
import { API_URL, DEFAULT_DIAGNOSES_ID, S3_URL } from '@/test/mocks/handlers'
import { requestLog } from '@/test/mocks/requestLog'
import { errorResponse, s3Response } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'

// MSW 서버와 공통 핸들러, 요청 기록, 응답 오버라이드가 의도대로 동작하는지 확인한다. (실제 api 함수를 그대로 호출한다)
describe('MSW 공통 핸들러', () => {
  it('presigned URL 발급: 요청한 파일 순서대로 key와 URL을 만들어 준다', async () => {
    const files = await requestPresignedUrls([
      { type: 'PRODUCT_MAIN', fileName: 'main.png', fileSize: 10 },
      { type: 'PRODUCT_DETAIL', fileName: 'detail.png', fileSize: 20 },
    ])

    expect(files.map((file) => file.key)).toEqual(['uploads/0-main.png', 'uploads/1-detail.png'])
    expect(files[0].presignedUrl).toBe(`${S3_URL}/uploads/0-main.png`)
  })

  it('S3 업로드(PUT): 성공하고 Content-Type 헤더를 기록한다', async () => {
    const file = new File(['image-bytes'], 'a.png', { type: 'image/png' })

    await putToS3(`${S3_URL}/uploads/0-a.png`, file, 'image/png')

    const [put] = requestLog.find('PUT', '/uploads/0-a.png')
    expect(put.headers.get('content-type')).toBe('image/png')
  })

  it('진단 제출: diagnosesId를 돌려주고 보낸 본문을 기록한다', async () => {
    const products = [{ productName: '이어폰', sourceType: 'URL', sourceUrl: 'https://example.com' }]

    const diagnosesId = await postDiagnosis(products as never)

    expect(diagnosesId).toBe(DEFAULT_DIAGNOSES_ID)
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({ products })
  })

  it('질문 답변 제출: 성공하고 보낸 답변 본문을 기록한다', async () => {
    const answers = [{ questionId: 'q1', answerText: '네' }]

    await expect(submitAnswers('product-1', answers)).resolves.toBeUndefined()

    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({ answers })
  })

  it('상품 단건 조회: 요청한 productId로 답변 대기 중인 상품을 돌려준다', async () => {
    const product = await getProduct('product-42')

    expect(product.productId).toBe('product-42')
    expect(product.processingStatus).toBe(ProcessingStatusType.AwaitingInput)
    expect(product.questions).toHaveLength(1)
  })
})

describe('응답 오버라이드', () => {
  it('server.use로 특정 요청만 실패 응답으로 덮어쓸 수 있다', async () => {
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(400, { code: 'COMMON-001', detailMessage: '상품 정보가 올바르지 않습니다.' })))

    const error = await postDiagnosis([]).catch((e: unknown) => e)

    expect(axios.isAxiosError(error)).toBe(true)
    expect(getErrorMessage(error, '기본 메시지')).toBe('상품 정보가 올바르지 않습니다.')
  })

  it('오버라이드는 그 테스트에만 적용되고, 다음 테스트에서는 기본(성공) 응답으로 돌아간다', async () => {
    await expect(postDiagnosis([])).resolves.toBe(DEFAULT_DIAGNOSES_ID)
  })

  it('한 요청만 덮어써도 나머지 요청은 기본 핸들러를 쓴다', async () => {
    server.use(http.post(`${API_URL}/api/v1/products/:productId/answers`, () => errorResponse(500)))

    await expect(submitAnswers('product-1', [])).rejects.toThrow()
    await expect(postDiagnosis([])).resolves.toBe(DEFAULT_DIAGNOSES_ID)
  })
})

describe('진단 파이프라인 전체(submitDiagnosis)를 MSW로 돌린다', () => {
  const makeProduct = (): Product => ({
    id: '1',
    type: SourceType.Url,
    title: '이어폰',
    link: 'https://example.com/item',
    productImageFile: new File(['image-bytes'], 'main.png', { type: 'image/png' }),
  })

  it('presigned 발급 → S3 업로드 → 진단 제출 순서로 요청하고, 발급된 key를 payload에 담는다', async () => {
    const diagnosesId = await submitDiagnosis([makeProduct()])

    expect(diagnosesId).toBe(DEFAULT_DIAGNOSES_ID)
    expect(requestLog.all().map((entry) => `${entry.method} ${entry.pathname}`)).toEqual([
      'POST /api/v1/presigned-url',
      'PUT /uploads/0-main.png',
      'POST /api/v1/diagnoses',
    ])
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({
      products: [{ productName: '이어폰', productImageKey: 'uploads/0-main.png', sourceType: SourceType.Url, sourceUrl: 'https://example.com/item' }],
    })
  })

  it('S3 업로드가 실패하면 진단 제출까지 가지 않고 해당 상품의 실패로 알린다', async () => {
    server.use(http.put(`${S3_URL}/*`, () => s3Response(403)))

    await expect(submitDiagnosis([makeProduct()])).rejects.toThrow('다음 상품의 진단 요청에 실패했습니다: 이어폰(')
    expect(requestLog.find('POST', '/api/v1/diagnoses')).toHaveLength(0)
  })

  it('진단 제출이 실패하면 서버의 오류 메시지를 그대로 전달한다', async () => {
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(400, { detailMessage: '상품은 최대 10개까지 담을 수 있어요.' })))

    const error = await submitDiagnosis([makeProduct()]).catch((e: unknown) => e)

    expect(getErrorMessage(error, '기본 메시지')).toBe('상품은 최대 10개까지 담을 수 있어요.')
  })
})

describe('요청 기록', () => {
  it('같은 요청을 여러 번 보내면 보낸 순서대로 기록한다', async () => {
    await submitAnswers('product-1', [{ questionId: 'q1', answerText: '첫째' }])
    await submitAnswers('product-1', [{ questionId: 'q1', answerText: '둘째' }])

    const bodies = requestLog.find('POST', '/api/v1/products/product-1/answers').map((entry) => entry.body)
    expect(bodies).toEqual([{ answers: [{ questionId: 'q1', answerText: '첫째' }] }, { answers: [{ questionId: 'q1', answerText: '둘째' }] }])
  })

  it('기록은 테스트마다 초기화된다', () => {
    expect(requestLog.all()).toEqual([])
  })
})

describe('핸들러가 없는 요청', () => {
  it('실제 네트워크로 나가지 않고 MSW가 오류로 처리한다', async () => {
    // MSW가 미처리 요청을 console.error로 알린다. 출력은 막고, 알린 내용으로 MSW가 처리했는지 확인한다.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    await expect(axios.get(`${API_URL}/api/v1/unknown`)).rejects.toThrow()

    // 단순한 연결 실패와 구분하기 위해, 핸들러가 없어서 오류로 처리했다는 MSW 메시지를 확인한다.
    expect(consoleError.mock.calls.flat().join(' ')).toContain('without a matching request handler')
  })
})
