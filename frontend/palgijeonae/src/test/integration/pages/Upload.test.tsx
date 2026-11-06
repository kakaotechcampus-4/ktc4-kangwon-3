import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { SourceType } from '@/api/types'
import UploadPage from '@/pages/Upload'
import type { Product } from '@/pages/Upload/types'
import { API_URL, DEFAULT_DIAGNOSES_ID, S3_URL } from '@/test/mocks/handlers'
import { requestLog } from '@/test/mocks/requestLog'
import { errorResponse, s3Response, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

// 업로드 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// demoProducts를 주면 메인의 체험 버튼처럼 상품이 미리 담긴 채로 열린다.
const renderUploadPage = (demoProducts?: Product[]) =>
  renderWithProviders(<UploadPage />, {
    path: '/upload',
    route: { pathname: '/upload', state: demoProducts ? { demoProducts } : null },
    extraRoutes: <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />,
  })

const titleInput = () => screen.getByLabelText('제품명')
const linkInput = () => screen.getByLabelText('제품 상세페이지 링크')
const contentInput = () => screen.getByLabelText('제품 상세페이지 내용')
const addButton = () => screen.getByRole('button', { name: '상품 추가하기' })
const startButton = () => screen.getByRole('button', { name: '진단 시작하기' })
const mainImageInput = () => document.getElementById('product-image') as HTMLInputElement

type User = ReturnType<typeof userEvent.setup>

// 긴 문자열은 한 글자씩 입력하면 느려서 붙여넣기로 채운다.
const fill = async (user: User, input: HTMLElement, text: string) => {
  await user.click(input)
  await user.paste(text)
}

const addUrlProduct = async (user: User, title: string, link = 'https://example.com/item') => {
  await fill(user, titleInput(), title)
  await fill(user, linkInput(), link)
  await user.click(addButton())
}

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
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '블루투스 이어폰')

    expect(screen.getByRole('heading', { name: '확인할 제품' })).toBeInTheDocument()
    expect(screen.getByText('블루투스 이어폰')).toBeInTheDocument()
    expect(titleInput()).toHaveValue('')
    expect(linkInput()).toHaveValue('')
    expect(window.alert).not.toHaveBeenCalled()
  })

  it('상품을 계속 추가하면 추가한 순서대로 쌓인다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '첫째')
    await addUrlProduct(user, '둘째')

    const titles = screen.getAllByText(/^(첫째|둘째)$/).map((element) => element.textContent)
    expect(titles).toEqual(['첫째', '둘째'])
  })

  it('텍스트/이미지 탭에서 내용으로 상품을 추가하고, 자세히 보기에서 내용을 확인한다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.click(screen.getByRole('button', { name: '텍스트 / 이미지' }))
    await fill(user, titleInput(), '캠핑 테이블')
    await fill(user, contentInput(), '접이식 알루미늄 테이블입니다.')
    await user.click(addButton())

    expect(screen.getByText('캠핑 테이블')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '자세히 보기' }))
    expect(screen.getByText('접이식 알루미늄 테이블입니다.')).toBeInTheDocument()
  })

  it('URL 상품의 자세히 보기에서 링크를 새 탭으로 열 수 있는 a 태그로 보여준다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '이어폰', 'https://example.com/item')
    await user.click(screen.getByRole('button', { name: '자세히 보기' }))

    const link = screen.getByRole('link', { name: 'https://example.com/item' })
    expect(link).toHaveAttribute('href', 'https://example.com/item')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('긴 제품명은 목록에서 40자로 줄여 보여주고, 원본은 title 속성에 둔다', async () => {
    const user = userEvent.setup()
    renderUploadPage()
    const longTitle = '가'.repeat(45)

    await addUrlProduct(user, longTitle)

    const heading = screen.getByRole('heading', { name: `${'가'.repeat(40)}...` })
    expect(heading).toHaveAttribute('title', longTitle)
  })

  it('대표 사진을 첨부하면 미리보기가 보이고, 상품 카드의 썸네일로 쓴다', async () => {
    const user = userEvent.setup()
    renderUploadPage()
    const image = makeImage()

    await user.upload(mainImageInput(), image)

    expect(screen.getByRole('heading', { name: '첨부된 제품 대표 사진' })).toBeInTheDocument()
    expect(URL.createObjectURL).toHaveBeenCalledWith(image)

    await fill(user, titleInput(), '이어폰')
    await fill(user, linkInput(), 'https://example.com/item')
    await user.click(addButton())

    expect(screen.getByAltText('상품 썸네일')).toHaveAttribute('src', 'blob:mock-object-url')
    // 상품을 추가하면 첨부 미리보기도 비워진다.
    expect(screen.queryByRole('heading', { name: '첨부된 제품 대표 사진' })).not.toBeInTheDocument()
  })

  it('상품이 10개가 되면 입력 폼 대신 안내 문구를 보여준다', () => {
    renderUploadPage(Array.from({ length: 10 }, (_, index) => makeDemoProduct(index + 1)))

    expect(screen.getByText('상품은 최대 10개까지 담을 수 있어요. 진단을 시작해주세요.')).toBeInTheDocument()
    expect(screen.queryByLabelText('제품명')).not.toBeInTheDocument()
  })

  it('체험 버튼처럼 미리 담아 둔 상품이 있으면 처음부터 목록에 보인다', () => {
    renderUploadPage([makeDemoProduct(1), makeDemoProduct(2)])

    expect(screen.getByText('상품 1')).toBeInTheDocument()
    expect(screen.getByText('상품 2')).toBeInTheDocument()
  })
})

describe('업로드 화면 - 상품 삭제', () => {
  it('삭제 버튼을 누르면 그 상품만 목록에서 사라진다', async () => {
    const user = userEvent.setup()
    renderUploadPage([makeDemoProduct(1), makeDemoProduct(2), makeDemoProduct(3)])

    await user.click(screen.getAllByRole('button', { name: '삭제' })[1])

    expect(screen.getByText('상품 1')).toBeInTheDocument()
    expect(screen.queryByText('상품 2')).not.toBeInTheDocument()
    expect(screen.getByText('상품 3')).toBeInTheDocument()
  })

  it('마지막 상품까지 삭제하면 목록 영역이 사라진다', async () => {
    const user = userEvent.setup()
    renderUploadPage([makeDemoProduct(1)])

    await user.click(screen.getByRole('button', { name: '삭제' }))

    expect(screen.queryByRole('heading', { name: '확인할 제품' })).not.toBeInTheDocument()
  })

  it('10개에서 하나를 삭제하면 입력 폼이 다시 나타난다', async () => {
    const user = userEvent.setup()
    renderUploadPage(Array.from({ length: 10 }, (_, index) => makeDemoProduct(index + 1)))

    await user.click(screen.getAllByRole('button', { name: '삭제' })[0])

    expect(screen.getByLabelText('제품명')).toBeInTheDocument()
    expect(screen.queryByText('상품은 최대 10개까지 담을 수 있어요. 진단을 시작해주세요.')).not.toBeInTheDocument()
  })
})

describe('업로드 화면 - 입력 방식 탭', () => {
  it('탭을 바꾸면 입력해 둔 값이 모두 비워진다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await fill(user, titleInput(), '이어폰')
    await fill(user, linkInput(), 'https://example.com/item')
    await user.upload(mainImageInput(), makeImage())

    await user.click(screen.getByRole('button', { name: '텍스트 / 이미지' }))

    expect(titleInput()).toHaveValue('')
    expect(contentInput()).toHaveValue('')
    expect(screen.queryByRole('heading', { name: '첨부된 제품 대표 사진' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'URL' }))
    expect(linkInput()).toHaveValue('')
  })

  it('같은 탭을 다시 눌러도 입력값은 유지된다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await fill(user, titleInput(), '이어폰')
    await user.click(screen.getByRole('button', { name: 'URL' }))

    expect(titleInput()).toHaveValue('이어폰')
  })
})

describe('업로드 화면 - 입력 검증', () => {
  it('제품명이 비어 있으면 안내하고 추가하지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await fill(user, linkInput(), 'https://example.com/item')
    await user.click(addButton())

    expect(window.alert).toHaveBeenCalledWith('제품명을 입력해주세요.')
    expect(screen.queryByRole('heading', { name: '확인할 제품' })).not.toBeInTheDocument()
  })

  it('링크가 비어 있으면 안내하고 추가하지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await fill(user, titleInput(), '이어폰')
    await user.click(addButton())

    expect(window.alert).toHaveBeenCalledWith('상세페이지 링크를 입력해주세요.')
    expect(screen.queryByRole('heading', { name: '확인할 제품' })).not.toBeInTheDocument()
  })

  it.each(['abc', 'www.example.com', '/mypage', 'javascript:alert(1)'])('링크가 http(s)로 시작하지 않으면 안내한다: %s', async (link) => {
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '이어폰', link)

    expect(window.alert).toHaveBeenCalledWith('상세페이지 링크는 http:// 또는 https://로 시작해야 합니다.')
    expect(screen.queryByRole('heading', { name: '확인할 제품' })).not.toBeInTheDocument()
  })

  it('입력 검증에 실패해도 입력해 둔 값은 지워지지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '이어폰', 'abc')

    expect(titleInput()).toHaveValue('이어폰')
    expect(linkInput()).toHaveValue('abc')
  })

  it('텍스트/이미지 입력에서 내용이 비어 있으면 안내하고 추가하지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.click(screen.getByRole('button', { name: '텍스트 / 이미지' }))
    await fill(user, titleInput(), '캠핑 테이블')
    await user.click(addButton())

    expect(window.alert).toHaveBeenCalledWith('상세페이지 내용을 입력해주세요.')
    expect(screen.queryByRole('heading', { name: '확인할 제품' })).not.toBeInTheDocument()
  })

  it('허용되지 않는 형식의 이미지는 첨부되지 않고 안내한다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.upload(mainImageInput(), makeImage('animation.gif', 'image/gif'))

    expect(window.alert).toHaveBeenCalledWith('jpeg, jpg, png, webp 형식의 이미지만 첨부할 수 있습니다.')
    expect(screen.queryByRole('heading', { name: '첨부된 제품 대표 사진' })).not.toBeInTheDocument()
  })

  it('10MB를 넘는 이미지는 첨부되지 않고 안내한다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.upload(mainImageInput(), makeImage('big.png', 'image/png', 10 * 1024 * 1024 + 1))

    expect(window.alert).toHaveBeenCalledWith('이미지는 1장당 10MB까지만 첨부할 수 있습니다.')
    expect(screen.queryByRole('heading', { name: '첨부된 제품 대표 사진' })).not.toBeInTheDocument()
  })
})

describe('업로드 화면 - 진단 요청', () => {
  it('담은 상품이 없으면 안내하고 요청을 보내지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.click(startButton())

    expect(window.alert).toHaveBeenCalledWith('진단할 상품을 먼저 추가해주세요.')
    expect(requestLog.all()).toEqual([])
  })

  it('담긴 상품 중 검증에 실패하는 것이 있으면 그 상품 이름과 사유를 안내하고 요청을 보내지 않는다', async () => {
    const user = userEvent.setup()
    renderUploadPage([makeDemoProduct(1), makeDemoProduct(2, { link: 'abc' })])

    await user.click(startButton())

    expect(window.alert).toHaveBeenCalledWith('상품 2: 상세페이지 링크는 http:// 또는 https://로 시작해야 합니다.')
    expect(requestLog.all()).toEqual([])
  })

  it('성공하면 진단 요청을 보내고 진단 진행 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await addUrlProduct(user, '이어폰', 'https://example.com/item')
    await user.click(startButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe(`/judgement/${DEFAULT_DIAGNOSES_ID}`)
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({
      products: [{ productName: '이어폰', sourceType: SourceType.Url, sourceUrl: 'https://example.com/item' }],
    })
    expect(window.alert).not.toHaveBeenCalled()
  })

  it('텍스트/이미지 상품은 내용과 이미지 key 목록으로 요청한다', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await user.click(screen.getByRole('button', { name: '텍스트 / 이미지' }))
    await fill(user, titleInput(), '캠핑 테이블')
    await fill(user, contentInput(), '접이식 테이블')
    await user.click(addButton())
    await user.click(startButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/diagnoses')[0].body).toEqual({
      products: [{ productName: '캠핑 테이블', sourceType: SourceType.TextImage, sourceText: '접이식 테이블', imageKeys: [] }],
    })
  })

  it('대표 사진이 있으면 presigned URL 발급 → S3 업로드 → 진단 제출 순서로 요청하고 발급된 key를 담는다', async () => {
    const user = userEvent.setup()
    renderUploadPage()
    const image = makeImage('main.png')

    await user.upload(mainImageInput(), image)
    await addUrlProduct(user, '이어폰')
    await user.click(startButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
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
    const user = userEvent.setup()
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.post(`${API_URL}/api/v1/diagnoses`, async () => {
        await gate
        return successResponse({ diagnosesId: 'diagnoses-late' })
      }),
    )
    renderUploadPage([makeDemoProduct(1)])

    await user.click(startButton())

    expect(await screen.findByRole('status', { name: '진단 요청을 보내는 중...' })).toBeInTheDocument()
    expect(screen.queryByLabelText('제품명')).not.toBeInTheDocument()

    release()

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-late')
  })

  it('진단 요청이 실패하면 서버의 오류 메시지를 안내하고, 화면과 담은 상품은 그대로 둔다', async () => {
    const user = userEvent.setup()
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(400, { detailMessage: '진단할 수 없는 상품입니다.' })))
    renderUploadPage([makeDemoProduct(1)])

    await user.click(startButton())

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('진단할 수 없는 상품입니다.'))
    expect(getCurrentLocation()).toBe('/upload')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByLabelText('제품명')).toBeInTheDocument()
    expect(screen.getByText('상품 1')).toBeInTheDocument()
  })

  it('이미지 업로드(S3)가 실패하면 진단 제출 없이 어떤 상품에서 실패했는지 안내한다', async () => {
    const user = userEvent.setup()
    server.use(http.put(`${S3_URL}/*`, () => s3Response(403)))
    renderUploadPage([makeDemoProduct(1, { title: '이어폰', productImageFile: makeImage() })])

    await user.click(startButton())

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('다음 상품의 진단 요청에 실패했습니다: 이어폰(')))
    expect(requestLog.find('POST', '/api/v1/diagnoses')).toHaveLength(0)
    expect(getCurrentLocation()).toBe('/upload')
  })

  it('실패한 뒤 다시 시도하면 성공해서 진단 진행 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    server.use(http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(500), { once: true }))
    renderUploadPage([makeDemoProduct(1)])

    await user.click(startButton())
    await waitFor(() => expect(window.alert).toHaveBeenCalledTimes(1))
    expect(getCurrentLocation()).toBe('/upload')

    await user.click(startButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe(`/judgement/${DEFAULT_DIAGNOSES_ID}`)
  })
})
