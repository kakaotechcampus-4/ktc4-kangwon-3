import { screen } from '@testing-library/react'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { SourceType } from '@/api/types'
import UploadPage from '@/pages/Upload'
import { MAX_FILE_SIZE_BYTES } from '@/pages/Upload/constants'
import type { Product } from '@/pages/Upload/types'
import { SERVER_MESSAGES, UPLOAD_MESSAGES } from '@/test/constants/messages'
import { uploadPage } from '@/test/drivers/uploadPage'
import { API_URL, DEFAULT_DIAGNOSES_ID, S3_URL } from '@/test/mocks/handlers'
import { requestLog } from '@/test/mocks/requestLog'
import { errorResponse, s3Response, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { createGate } from '@/test/utils/createGate'
import { expectNotified, expectNotNotified, waitForNotificationCount, waitForNotified } from '@/test/utils/notifications'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

// 업로드 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(uploadPage)를 거친다. demoProducts를 주면 메인의 체험 버튼처럼 상품이 미리 담긴 채로 열린다.
const renderUploadPage = (demoProducts?: Product[]) => {
  renderWithProviders(<UploadPage />, {
    path: '/upload',
    route: { pathname: '/upload', state: demoProducts ? { demoProducts } : null },
    extraRoutes: <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />,
  })
  return uploadPage()
}

// 진단 진행 화면으로 이동했는지 확인한다. (이 파일이 만든 도착 화면)
const findJudgementScreen = () => screen.findByText('진단 진행 화면')

const makeImage = (name = 'main.png', type = 'image/png', size?: number) => {
  const file = new File(['image-bytes'], name, { type })
  if (size !== undefined) {
    Object.defineProperty(file, 'size', { value: size })
  }
  return file
}

const makeDemoProduct = (index: number, overrides: Partial<Product> = {}): Product => ({
  id: `demo-${index}`,
  type: SourceType.Url,
  title: `상품 ${index}`,
  link: `https://example.com/${index}`,
  ...overrides,
})

describe('업로드 화면 - 상품 추가', () => {
  it('URL 상품을 추가하면 목록에 보이고 입력 폼은 비워진다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '블루투스 이어폰' })

    expect(page.productNames()).toEqual(['블루투스 이어폰'])
    expect(page.titleValue()).toBe('')
    expect(page.linkValue()).toBe('')
    expectNotNotified()
  })

  it('상품을 계속 추가하면 추가한 순서대로 쌓인다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '첫째' })
    await page.addUrlProduct({ title: '둘째' })

    expect(page.productNames()).toEqual(['첫째', '둘째'])
  })

  it('텍스트/이미지 탭에서 내용으로 상품을 추가하고, 자세히 보기에서 내용을 확인한다', async () => {
    const page = renderUploadPage()

    await page.switchToTextImage()
    await page.addTextImageProduct({ title: '캠핑 테이블', content: '접이식 알루미늄 테이블입니다.' })

    expect(page.productNames()).toEqual(['캠핑 테이블'])

    await page.openDetail('캠핑 테이블')
    expect(page.hasDetailContent('접이식 알루미늄 테이블입니다.')).toBe(true)
  })

  it('URL 상품의 자세히 보기에서 링크를 새 탭으로 열 수 있는 a 태그로 보여준다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '이어폰', link: 'https://example.com/item' })
    await page.openDetail('이어폰')

    expect(page.detailLink('https://example.com/item')).toEqual({
      href: 'https://example.com/item',
      target: '_blank',
      rel: 'noopener noreferrer',
    })
  })

  // 말줄임 규칙(글자 수 경계, 이모지 등)은 단위 테스트가 다룬다. (unit/lib/text.test.ts) 여기서는 목록에서 줄여 보이고 원본이 보존되는지만 확인한다.
  it('긴 제품명은 목록에서 줄여 보여주고, 원본은 title 속성에 보존한다', async () => {
    const page = renderUploadPage()
    const longTitle = '가'.repeat(60)

    await page.addUrlProduct({ title: longTitle })

    const [shownTitle] = page.productNames()
    expect(shownTitle).toMatch(/\.\.\.$/)
    expect(shownTitle.length).toBeLessThan(longTitle.length)
    expect(page.productTooltip(shownTitle)).toBe(longTitle)
  })

  it('대표 사진을 첨부하면 미리보기가 보이고, 상품 카드의 썸네일로 쓴다', async () => {
    const page = renderUploadPage()
    const image = makeImage()

    await page.attachMainImage(image)

    expect(page.hasAttachedImage()).toBe(true)
    expect(URL.createObjectURL).toHaveBeenCalledWith(image)

    await page.addUrlProduct({ title: '이어폰', link: 'https://example.com/item' })

    expect(page.thumbnailSrc('이어폰')).toBe('blob:mock-object-url')
    // 상품을 추가하면 첨부 미리보기도 비워진다.
    expect(page.hasAttachedImage()).toBe(false)
  })

  it('상품이 10개가 되면 입력 폼 대신 안내 문구를 보여준다', () => {
    const page = renderUploadPage(Array.from({ length: 10 }, (_, index) => makeDemoProduct(index + 1)))

    expect(page.hasMaxProductsNotice()).toBe(true)
    expect(page.isFormVisible()).toBe(false)
  })

  it('체험 버튼처럼 미리 담아 둔 상품이 있으면 처음부터 목록에 보인다', () => {
    const page = renderUploadPage([makeDemoProduct(1), makeDemoProduct(2)])

    expect(page.productNames()).toEqual(['상품 1', '상품 2'])
  })
})

describe('업로드 화면 - 상품 삭제', () => {
  it('삭제 버튼을 누르면 그 상품만 목록에서 사라진다', async () => {
    const page = renderUploadPage([makeDemoProduct(1), makeDemoProduct(2), makeDemoProduct(3)])

    await page.removeProduct('상품 2')

    expect(page.productNames()).toEqual(['상품 1', '상품 3'])
  })

  it('마지막 상품까지 삭제하면 목록 영역이 사라진다', async () => {
    const page = renderUploadPage([makeDemoProduct(1)])

    await page.removeProduct('상품 1')

    expect(page.productNames()).toEqual([])
  })

  it('10개에서 하나를 삭제하면 입력 폼이 다시 나타난다', async () => {
    const page = renderUploadPage(Array.from({ length: 10 }, (_, index) => makeDemoProduct(index + 1)))

    await page.removeProduct('상품 1')

    expect(page.isFormVisible()).toBe(true)
    expect(page.hasMaxProductsNotice()).toBe(false)
  })
})

describe('업로드 화면 - 입력 방식 탭', () => {
  it('탭을 바꾸면 입력해 둔 값이 모두 비워진다', async () => {
    const page = renderUploadPage()

    await page.fillTitle('이어폰')
    await page.fillLink('https://example.com/item')
    await page.attachMainImage(makeImage())

    await page.switchToTextImage()

    expect(page.titleValue()).toBe('')
    expect(page.contentValue()).toBe('')
    expect(page.hasAttachedImage()).toBe(false)

    await page.switchToUrl()
    expect(page.linkValue()).toBe('')
  })

  it('같은 탭을 다시 눌러도 입력값은 유지된다', async () => {
    const page = renderUploadPage()

    await page.fillTitle('이어폰')
    await page.switchToUrl()

    expect(page.titleValue()).toBe('이어폰')
  })
})

describe('업로드 화면 - 입력 검증', () => {
  it('제품명이 비어 있으면 안내하고 추가하지 않는다', async () => {
    const page = renderUploadPage()

    await page.fillLink('https://example.com/item')
    await page.clickAddProduct()

    expectNotified(UPLOAD_MESSAGES.TITLE_REQUIRED)
    expect(page.productNames()).toEqual([])
  })

  it('링크가 비어 있으면 안내하고 추가하지 않는다', async () => {
    const page = renderUploadPage()

    await page.fillTitle('이어폰')
    await page.clickAddProduct()

    expectNotified(UPLOAD_MESSAGES.LINK_REQUIRED)
    expect(page.productNames()).toEqual([])
  })

  // 어떤 형식이 http(s)가 아닌지는 단위 테스트가 다룬다. (unit/pages/Upload/validation.test.ts, unit/lib/url.test.ts) 여기서는 화면에 안내가 뜨는지만 확인한다.
  it('링크가 http(s)로 시작하지 않으면 안내하고 추가하지 않는다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '이어폰', link: 'www.example.com' })

    expectNotified(UPLOAD_MESSAGES.LINK_MUST_BE_HTTP)
    expect(page.productNames()).toEqual([])
  })

  it('입력 검증에 실패해도 입력해 둔 값은 지워지지 않는다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '이어폰', link: 'abc' })

    expect(page.titleValue()).toBe('이어폰')
    expect(page.linkValue()).toBe('abc')
  })

  it('텍스트/이미지 입력에서 내용이 비어 있으면 안내하고 추가하지 않는다', async () => {
    const page = renderUploadPage()

    await page.switchToTextImage()
    await page.fillTitle('캠핑 테이블')
    await page.clickAddProduct()

    expectNotified(UPLOAD_MESSAGES.CONTENT_REQUIRED)
    expect(page.productNames()).toEqual([])
  })

  it('허용되지 않는 형식의 이미지는 첨부되지 않고 안내한다', async () => {
    const page = renderUploadPage()

    await page.attachMainImage(makeImage('animation.gif', 'image/gif'))

    expectNotified(UPLOAD_MESSAGES.IMAGE_TYPE_NOT_ALLOWED)
    expect(page.hasAttachedImage()).toBe(false)
  })

  it('10MB를 넘는 이미지는 첨부되지 않고 안내한다', async () => {
    const page = renderUploadPage()

    await page.attachMainImage(makeImage('big.png', 'image/png', MAX_FILE_SIZE_BYTES + 1))

    expectNotified(UPLOAD_MESSAGES.IMAGE_TOO_LARGE)
    expect(page.hasAttachedImage()).toBe(false)
  })
})

describe('업로드 화면 - 진단 요청', () => {
  it('담은 상품이 없으면 안내하고 요청을 보내지 않는다', async () => {
    const page = renderUploadPage()

    await page.startDiagnosis()

    expectNotified(UPLOAD_MESSAGES.NO_PRODUCTS)
    expect(requestLog.all()).toEqual([])
  })

  it('담긴 상품 중 검증에 실패하는 것이 있으면 그 상품 이름과 사유를 안내하고 요청을 보내지 않는다', async () => {
    const page = renderUploadPage([makeDemoProduct(1), makeDemoProduct(2, { link: 'abc' })])

    await page.startDiagnosis()

    expectNotified(UPLOAD_MESSAGES.invalidProduct('상품 2', UPLOAD_MESSAGES.LINK_MUST_BE_HTTP))
    expect(requestLog.all()).toEqual([])
  })

  it('성공하면 진단 요청을 보내고 진단 진행 화면으로 이동한다', async () => {
    const page = renderUploadPage()

    await page.addUrlProduct({ title: '이어폰', link: 'https://example.com/item' })
    await page.startDiagnosis()

    expect(await findJudgementScreen()).toBeInTheDocument()
    expect(getCurrentLocation()).toBe(`/judgement/${DEFAULT_DIAGNOSES_ID}`)
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({
      products: [{ productName: '이어폰', sourceType: SourceType.Url, sourceUrl: 'https://example.com/item' }],
    })
    expectNotNotified()
  })

  it('텍스트/이미지 상품은 내용과 이미지 key 목록으로 요청한다', async () => {
    const page = renderUploadPage()

    await page.switchToTextImage()
    await page.addTextImageProduct({ title: '캠핑 테이블', content: '접이식 테이블' })
    await page.startDiagnosis()

    expect(await findJudgementScreen()).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({
      products: [{ productName: '캠핑 테이블', sourceType: SourceType.TextImage, sourceText: '접이식 테이블', imageKeys: [] }],
    })
  })

  it('대표 사진이 있으면 presigned URL 발급 → S3 업로드 → 진단 제출 순서로 요청하고 발급된 key를 담는다', async () => {
    const page = renderUploadPage()
    const image = makeImage('main.png')

    await page.attachMainImage(image)
    await page.addUrlProduct({ title: '이어폰' })
    await page.startDiagnosis()

    expect(await findJudgementScreen()).toBeInTheDocument()
    expect(requestLog.all().map((entry) => `${entry.method} ${entry.pathname}`)).toEqual([
      'POST /api/v1/presigned-url',
      'PUT /uploads/0-main.png',
      'POST /api/v1/diagnoses',
    ])
    expect(requestLog.find('POST', '/api/v1/presigned-url')[0].body).toEqual({
      files: [{ type: 'PRODUCT_MAIN', fileName: 'main.png', fileSize: image.size }],
    })
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toMatchObject({
      products: [{ productName: '이어폰', productImageKey: 'uploads/0-main.png' }],
    })
  })

  it('요청을 보내는 동안에는 로딩을 보여주고 입력 폼을 숨긴다', async () => {
    const gate = createGate()
    server.use(
      http.post(`${API_URL}/api/v1/diagnoses`, async () => {
        await gate.promise
        return successResponse({ diagnosesId: 'diagnoses-late' })
      }),
    )
    const page = renderUploadPage([makeDemoProduct(1)])

    await page.startDiagnosis()

    await page.waitUntilSubmitting()
    expect(page.isSubmitting()).toBe(true)
    expect(page.isFormVisible()).toBe(false)

    gate.release()

    expect(await findJudgementScreen()).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-late')
  })

  it('진단 요청이 실패하면 서버의 오류 메시지를 안내하고, 화면과 담은 상품은 그대로 둔다', async () => {
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.DIAGNOSIS_REJECTED })))
    const page = renderUploadPage([makeDemoProduct(1)])

    await page.startDiagnosis()

    await waitForNotified(SERVER_MESSAGES.DIAGNOSIS_REJECTED)
    expect(getCurrentLocation()).toBe('/upload')
    expect(page.isSubmitting()).toBe(false)
    expect(page.isFormVisible()).toBe(true)
    expect(page.productNames()).toEqual(['상품 1'])
  })

  it('이미지 업로드(S3)가 실패하면 진단 제출 없이 어떤 상품에서 실패했는지 안내한다', async () => {
    server.use(http.put(`${S3_URL}/*`, () => s3Response(403)))
    const page = renderUploadPage([makeDemoProduct(1, { title: '이어폰', productImageFile: makeImage() })])

    await page.startDiagnosis()

    await waitForNotified({ includes: UPLOAD_MESSAGES.productRequestFailed('이어폰') })
    expect(requestLog.find('POST', '/api/v1/diagnoses')).toHaveLength(0)
    expect(getCurrentLocation()).toBe('/upload')
  })

  it('실패한 뒤 다시 시도하면 성공해서 진단 진행 화면으로 이동한다', async () => {
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(500), { once: true }))
    const page = renderUploadPage([makeDemoProduct(1)])

    await page.startDiagnosis()
    await waitForNotificationCount(1)
    expect(getCurrentLocation()).toBe('/upload')

    await page.startDiagnosis()

    expect(await findJudgementScreen()).toBeInTheDocument()
    expect(getCurrentLocation()).toBe(`/judgement/${DEFAULT_DIAGNOSES_ID}`)
  })
})
