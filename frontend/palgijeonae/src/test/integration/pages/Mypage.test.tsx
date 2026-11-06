import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { ResultStatus } from '@/api/types'
import MyPage from '@/pages/Mypage'
import type { MyProductItem } from '@/pages/Mypage/types'
import { useAuthStore } from '@/store/useAuthStore'
import { buildMyProduct, buildUserInfo } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCTS_URL = `${API_URL}/api/v1/products`
const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`
const MY_INFO_URL = `${API_URL}/api/v1/users/me`

// 마이페이지를 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
const renderMyPage = () =>
  renderWithProviders(<MyPage />, {
    path: '/mypage',
    route: '/mypage',
    extraRoutes: (
      <>
        <Route path="/" element={<p>메인 화면</p>} />
        <Route path="/result/product/:productId" element={<p>결과 화면</p>} />
      </>
    ),
  })

type User = ReturnType<typeof userEvent.setup>

// 상품 이름이 서로 부분 문자열이 되지 않도록 번호를 두 자리로 맞춘다. (검색에서 '상품-01'이 '상품-10'에 걸리지 않게)
const makeProducts = (count: number, overrides: (index: number) => Partial<MyProductItem> = () => ({})): MyProductItem[] =>
  Array.from({ length: count }, (_, index) => {
    const number = index + 1
    return buildMyProduct({ productId: `product-${number}`, productName: `상품-${String(number).padStart(2, '0')}`, ...overrides(number) })
  })

// 서버처럼 동작하는 메모리 목록. GET은 쿼리(resultStatus, keyword, page, size)대로 거르고 나누고, DELETE는 목록에서 뺀다.
// beforeDelete를 주면 삭제 요청이 그 Promise를 기다린 뒤에 처리된다. ("삭제 중" 상태 확인용)
const mockProductServer = (initial: MyProductItem[], { beforeDelete }: { beforeDelete?: () => Promise<void> } = {}) => {
  let products = [...initial]
  server.use(
    http.get(PRODUCTS_URL, async ({ request }) => {
      await recordRequest(request)
      const params = new URL(request.url).searchParams
      const resultStatus = params.get('resultStatus')
      const keyword = params.get('keyword') ?? ''
      const page = Number(params.get('page') ?? 0)
      const size = Number(params.get('size') ?? 10)

      const filtered = products.filter((product) => (!resultStatus || product.resultStatus === resultStatus) && product.productName.includes(keyword))
      const totalPages = Math.max(1, Math.ceil(filtered.length / size))
      return successResponse({
        products: filtered.slice(page * size, (page + 1) * size),
        pageInfo: { page, size, totalElements: filtered.length, totalPages, hasNext: page + 1 < totalPages },
      })
    }),
    http.delete(PRODUCT_URL, async ({ request, params }) => {
      await recordRequest(request)
      await beforeDelete?.()
      products = products.filter((product) => product.productId !== params.productId)
      return successResponse(null)
    }),
  )
}

// 응답을 풀어 줄 때까지 붙잡아 두는 문. "요청 중" 상태를 확인할 때 쓴다.
const createGate = () => {
  let release!: () => void
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

const lastListQuery = () => new URL(requestLog.find('GET', '/api/v1/products').at(-1)!.url).searchParams
const visibleProductNames = () => screen.getAllByRole('heading', { level: 3, name: /^상품-\d+$/ }).map((heading) => heading.textContent)
const searchBox = () => screen.getByRole('textbox', { name: '상품명 검색' })
const deleteButton = (productName: string) => screen.getByRole('button', { name: `${productName} 삭제` })

const search = async (user: User, keyword: string) => {
  await user.click(searchBox())
  await user.paste(keyword)
  await user.keyboard('{Enter}')
}

describe('마이페이지 - 조회', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 회원 정보와 상품 목록을 보여준다', async () => {
    mockProductServer(makeProducts(3))
    renderMyPage()

    expect(screen.getAllByRole('status', { name: '로딩 중' })).toHaveLength(2)

    expect(await screen.findByText('홍길동')).toBeInTheDocument()
    expect(screen.getByText('gildong@example.com')).toBeInTheDocument()
    expect(screen.getByText('카카오 계정으로 가입')).toBeInTheDocument()
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-01', '상품-02', '상품-03']))
    expect(screen.queryByRole('status', { name: '로딩 중' })).not.toBeInTheDocument()
  })

  it('처음에는 필터 없이 첫 페이지를 최신순으로 조회한다', async () => {
    mockProductServer(makeProducts(3))
    renderMyPage()
    await screen.findByText('상품-01')

    const query = lastListQuery()
    expect(query.get('page')).toBe('0')
    expect(query.get('size')).toBe('10')
    expect(query.get('sortType')).toBe('LATEST')
    expect(query.has('resultStatus')).toBe(false)
    expect(query.has('keyword')).toBe(false)
  })

  it('상품을 누르면 그 상품의 결과 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(2))
    renderMyPage()

    await user.click(await screen.findByRole('link', { name: /상품-02/ }))

    expect(await screen.findByText('결과 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/result/product/product-2')
  })

  it('상품이 없으면 안내 문구를 보여준다', async () => {
    mockProductServer([])
    renderMyPage()

    expect(await screen.findByText('조건에 맞는 상품이 없어요.')).toBeInTheDocument()
  })

  it('목록 조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(2))
    server.use(http.get(PRODUCTS_URL, () => errorResponse(500), { once: true }))
    renderMyPage()

    expect(await screen.findByText('상품 목록을 불러오지 못했어요.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-01', '상품-02']))
    expect(screen.queryByText('상품 목록을 불러오지 못했어요.')).not.toBeInTheDocument()
  })

  it('회원 정보 조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(1))
    server.use(http.get(MY_INFO_URL, () => errorResponse(500), { once: true }))
    renderMyPage()

    expect(await screen.findByText('회원 정보를 불러오지 못했어요.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    expect(await screen.findByText('홍길동')).toBeInTheDocument()
  })
})

describe('마이페이지 - 검색', () => {
  it('검색어를 입력하고 Enter를 누르면 그 검색어로 조회한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(5))
    renderMyPage()
    await screen.findByText('상품-01')

    await search(user, '상품-03')

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-03']))
    expect(lastListQuery().get('keyword')).toBe('상품-03')
  })

  it('입력만 하고 Enter를 누르기 전에는 조회하지 않는다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(5))
    renderMyPage()
    await screen.findByText('상품-01')
    const requestCount = requestLog.find('GET', '/api/v1/products').length

    await user.click(searchBox())
    await user.paste('상품-03')

    expect(requestLog.find('GET', '/api/v1/products')).toHaveLength(requestCount)
    expect(visibleProductNames()).toHaveLength(5)
  })

  it('검색 버튼을 눌러도 검색한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(5))
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(searchBox())
    await user.paste('상품-02')
    await user.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-02']))
  })

  it('검색어를 모두 지우면 Enter 없이 바로 전체 목록으로 돌아간다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(5))
    renderMyPage()
    await screen.findByText('상품-01')
    await search(user, '상품-03')
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-03']))

    await user.clear(searchBox())

    await waitFor(() => expect(visibleProductNames()).toHaveLength(5))
    expect(lastListQuery().has('keyword')).toBe(false)
  })

  it('검색어 지우기 버튼을 누르면 검색어를 비우고 전체 목록으로 돌아간다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(5))
    renderMyPage()
    await screen.findByText('상품-01')
    await search(user, '상품-03')
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-03']))

    await user.click(screen.getByRole('button', { name: '검색어 지우기' }))

    await waitFor(() => expect(visibleProductNames()).toHaveLength(5))
    expect(searchBox()).toHaveValue('')
  })

  it('일치하는 상품이 없으면 안내 문구를 보여준다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(3))
    renderMyPage()
    await screen.findByText('상품-01')

    await search(user, '없는 상품')

    expect(await screen.findByText('조건에 맞는 상품이 없어요.')).toBeInTheDocument()
  })
})

describe('마이페이지 - 필터', () => {
  // 구매 대행 가능 3개, 사입 인증 필요 2개, 재확인 필요 1개
  const statusProducts = () =>
    makeProducts(6, (number) => ({
      resultStatus:
        number <= 3
          ? ResultStatus.PurchasingAgentAllowed
          : number <= 5
            ? ResultStatus.DirectImportCertificationRequired
            : ResultStatus.RecheckRequired,
    }))

  it('필터 탭을 누르면 그 결과 상태로 조회한다', async () => {
    const user = userEvent.setup()
    mockProductServer(statusProducts())
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(screen.getByRole('button', { name: '사입 인증 필요' }))

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-04', '상품-05']))
    expect(lastListQuery().get('resultStatus')).toBe(ResultStatus.DirectImportCertificationRequired)
  })

  it('다른 탭으로 바꾸거나 전체를 누르면 그에 맞게 다시 조회한다', async () => {
    const user = userEvent.setup()
    mockProductServer(statusProducts())
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(screen.getByRole('button', { name: '재확인 필요' }))
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-06']))
    expect(lastListQuery().get('resultStatus')).toBe(ResultStatus.RecheckRequired)

    await user.click(screen.getByRole('button', { name: '전체' }))
    await waitFor(() => expect(visibleProductNames()).toHaveLength(6))
    expect(lastListQuery().has('resultStatus')).toBe(false)
  })

  it('필터와 검색어를 함께 적용한다', async () => {
    const user = userEvent.setup()
    mockProductServer(statusProducts())
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(screen.getByRole('button', { name: '구매 대행 가능' }))
    await search(user, '상품-02')

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-02']))
    expect(lastListQuery().get('resultStatus')).toBe(ResultStatus.PurchasingAgentAllowed)
    expect(lastListQuery().get('keyword')).toBe('상품-02')
  })

  it('필터를 바꾸면 첫 페이지부터 다시 조회한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(25))
    renderMyPage()
    await screen.findByText('상품-01')
    await user.click(screen.getByRole('button', { name: '3' }))
    await waitFor(() => expect(lastListQuery().get('page')).toBe('2'))

    await user.click(screen.getByRole('button', { name: '구매 대행 가능' }))

    await waitFor(() => expect(lastListQuery().get('page')).toBe('0'))
  })

  it('검색어를 바꾸면 첫 페이지부터 다시 조회한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(25))
    renderMyPage()
    await screen.findByText('상품-01')
    await user.click(screen.getByRole('button', { name: '2' }))
    await waitFor(() => expect(lastListQuery().get('page')).toBe('1'))

    await search(user, '상품-')

    await waitFor(() => expect(lastListQuery().get('page')).toBe('0'))
  })
})

describe('마이페이지 - 페이지 이동', () => {
  it('상품이 한 페이지(10개) 이하면 페이지 이동 버튼을 보여주지 않는다', async () => {
    mockProductServer(makeProducts(10))
    renderMyPage()
    await screen.findByText('상품-01')

    expect(screen.queryByRole('button', { name: '다음' })).not.toBeInTheDocument()
  })

  it('페이지 번호를 누르면 그 페이지의 상품을 보여준다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(25))
    renderMyPage()
    await screen.findByText('상품-01')
    expect(visibleProductNames()).toHaveLength(10)

    await user.click(screen.getByRole('button', { name: '2' }))

    await waitFor(() => expect(visibleProductNames()[0]).toBe('상품-11'))
    expect(visibleProductNames()).toHaveLength(10)
    expect(lastListQuery().get('page')).toBe('1')
  })

  it('다음·이전·마지막·처음 버튼으로 이동하고, 끝에서는 해당 버튼이 비활성이 된다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(25))
    renderMyPage()
    await screen.findByText('상품-01')

    // 첫 페이지에서는 처음·이전이 비활성
    expect(screen.getByRole('button', { name: '처음' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '이전' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: '마지막 페이지' }))
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-21', '상품-22', '상품-23', '상품-24', '상품-25']))
    expect(lastListQuery().get('page')).toBe('2')
    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '마지막 페이지' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: '이전' }))
    await waitFor(() => expect(visibleProductNames()[0]).toBe('상품-11'))

    await user.click(screen.getByRole('button', { name: '처음' }))
    await waitFor(() => expect(visibleProductNames()[0]).toBe('상품-01'))
  })
})

describe('마이페이지 - 상품 삭제', () => {
  it('삭제 버튼을 누르면 상품 이름을 넣은 확인 문구를 보여준다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(3))
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(deleteButton('상품-02'))

    expect(window.confirm).toHaveBeenCalledWith("'상품-02'의 진단 결과와 첨부 이미지가 함께 삭제되고, 되돌릴 수 없어요.")
  })

  it('확인을 취소하면 삭제 요청을 보내지 않고 목록도 그대로다', async () => {
    const user = userEvent.setup()
    vi.mocked(window.confirm).mockReturnValue(false)
    mockProductServer(makeProducts(3))
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(deleteButton('상품-02'))

    expect(requestLog.find('DELETE', '/api/v1/products/product-2')).toHaveLength(0)
    expect(visibleProductNames()).toEqual(['상품-01', '상품-02', '상품-03'])
  })

  it('확인하면 삭제 요청을 보내고, 목록을 다시 불러와 그 상품만 사라진다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(3))
    renderMyPage()
    await screen.findByText('상품-01')
    const listRequestsBefore = requestLog.find('GET', '/api/v1/products').length

    await user.click(deleteButton('상품-02'))

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-01', '상품-03']))
    expect(requestLog.find('DELETE', '/api/v1/products/product-2')).toHaveLength(1)
    expect(requestLog.find('GET', '/api/v1/products').length).toBeGreaterThan(listRequestsBefore)
    expect(window.alert).not.toHaveBeenCalled()
  })

  it('삭제하는 동안에는 그 상품의 버튼만 "삭제 중"으로 비활성화한다', async () => {
    const user = userEvent.setup()
    const gate = createGate()
    mockProductServer(makeProducts(3), { beforeDelete: () => gate.promise })
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(deleteButton('상품-02'))

    await waitFor(() => expect(deleteButton('상품-02')).toBeDisabled())
    expect(screen.getByRole('button', { name: '상품-02 삭제' })).toHaveTextContent('삭제 중')
    expect(deleteButton('상품-01')).toBeEnabled()
    expect(deleteButton('상품-03')).toBeEnabled()

    gate.release()

    await waitFor(() => expect(screen.queryByRole('button', { name: '상품-02 삭제' })).not.toBeInTheDocument())
  })

  it('삭제에 실패하면 서버의 오류 메시지를 안내하고, 상품은 그대로 두며 버튼을 다시 활성화한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(3))
    server.use(http.delete(PRODUCT_URL, () => errorResponse(400, { detailMessage: '삭제할 수 없는 상품입니다.' })))
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(deleteButton('상품-02'))

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('삭제할 수 없는 상품입니다.'))
    expect(visibleProductNames()).toEqual(['상품-01', '상품-02', '상품-03'])
    expect(deleteButton('상품-02')).toBeEnabled()
    expect(deleteButton('상품-02')).toHaveTextContent('삭제')
  })

  it('마지막 페이지의 마지막 상품을 삭제하면 이전 페이지로 이동한다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(11))
    renderMyPage()
    await screen.findByText('상품-01')
    await user.click(screen.getByRole('button', { name: '2' }))
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-11']))

    await user.click(deleteButton('상품-11'))

    await waitFor(() => expect(visibleProductNames()).toHaveLength(10))
    expect(visibleProductNames()[0]).toBe('상품-01')
    expect(lastListQuery().get('page')).toBe('0')
    // 상품이 10개가 되어 페이지가 하나뿐이다.
    expect(screen.queryByRole('button', { name: '다음' })).not.toBeInTheDocument()
  })

  it('페이지에 상품이 남아 있으면 삭제해도 같은 페이지에 머문다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(12))
    renderMyPage()
    await screen.findByText('상품-01')
    await user.click(screen.getByRole('button', { name: '2' }))
    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-11', '상품-12']))

    await user.click(deleteButton('상품-11'))

    await waitFor(() => expect(visibleProductNames()).toEqual(['상품-12']))
    expect(lastListQuery().get('page')).toBe('1')
  })

  it('첫 페이지의 마지막 상품을 삭제하면 페이지는 그대로 두고 빈 목록 안내를 보여준다', async () => {
    const user = userEvent.setup()
    mockProductServer(makeProducts(1))
    renderMyPage()
    await screen.findByText('상품-01')

    await user.click(deleteButton('상품-01'))

    expect(await screen.findByText('조건에 맞는 상품이 없어요.')).toBeInTheDocument()
    expect(lastListQuery().get('page')).toBe('0')
  })
})

describe('마이페이지 - 이름 수정', () => {
  const renderProfile = async () => {
    mockProductServer(makeProducts(1))
    renderMyPage()
    await screen.findByText('홍길동')
  }

  const startEditing = async (user: User) => {
    await user.click(screen.getByRole('button', { name: '이름 수정' }))
    return screen.getByLabelText('이름')
  }

  const replaceName = async (user: User, input: HTMLElement, name: string) => {
    await user.clear(input)
    await user.paste(name)
  }

  it('수정 버튼을 누르면 현재 이름이 채워진 입력창으로 바뀐다', async () => {
    const user = userEvent.setup()
    await renderProfile()

    const input = await startEditing(user)

    expect(input).toHaveValue('홍길동')
    expect(input).toHaveFocus()
    expect(screen.getByRole('button', { name: '저장' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '취소' })).toBeInTheDocument()
  })

  it('새 이름을 저장하면 요청을 보내고, 화면에 새 이름이 보이며 편집이 끝난다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)

    await replaceName(user, input, '김철수')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByText('김철수')).toBeInTheDocument()
    expect(screen.queryByText('홍길동')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '이름 수정' })).toBeInTheDocument()
    expect(requestLog.find('PATCH', '/api/v1/users/me')[0].body).toEqual({ name: '김철수' })
  })

  it('이름 앞뒤 공백은 지워서 저장한다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)

    await replaceName(user, input, '  김철수  ')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByText('김철수')).toBeInTheDocument()
    expect(requestLog.find('PATCH', '/api/v1/users/me')[0].body).toEqual({ name: '김철수' })
  })

  it('이름이 그대로면 요청 없이 편집만 끝낸다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    await startEditing(user)

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(screen.getByRole('button', { name: '이름 수정' })).toBeInTheDocument()
    expect(requestLog.find('PATCH', '/api/v1/users/me')).toHaveLength(0)
  })

  it('이름을 비우거나 20자를 넘기면 저장 버튼을 비활성화한다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)

    await user.clear(input)
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()

    await replaceName(user, input, '가'.repeat(20))
    expect(screen.getByText('20/20')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()

    await replaceName(user, input, '가'.repeat(21))
    expect(screen.getByText('21/20')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
  })

  it('공백만 입력해도 저장 버튼을 비활성화한다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)

    await replaceName(user, input, '     ')

    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
  })

  it('취소하면 고치던 내용을 버리고 원래 이름으로 돌아가며 요청도 보내지 않는다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)
    await replaceName(user, input, '김철수')

    await user.click(screen.getByRole('button', { name: '취소' }))

    expect(screen.getByText('홍길동')).toBeInTheDocument()
    expect(requestLog.find('PATCH', '/api/v1/users/me')).toHaveLength(0)

    // 다시 수정을 시작하면 고치던 내용이 아니라 원래 이름이 채워진다.
    expect(await startEditing(user)).toHaveValue('홍길동')
  })

  it('Esc를 누르면 편집을 취소한다', async () => {
    const user = userEvent.setup()
    await renderProfile()
    const input = await startEditing(user)
    await replaceName(user, input, '김철수')

    await user.keyboard('{Escape}')

    expect(screen.getByText('홍길동')).toBeInTheDocument()
    expect(screen.queryByLabelText('이름')).not.toBeInTheDocument()
  })

  it('저장하는 동안에는 입력창과 버튼을 비활성화하고, 끝나면 편집이 닫힌다', async () => {
    const user = userEvent.setup()
    const gate = createGate()
    server.use(
      http.patch(MY_INFO_URL, async ({ request }) => {
        const { name } = await recordRequest<{ name: string }>(request)
        await gate.promise
        return successResponse(buildUserInfo({ name }))
      }),
    )
    await renderProfile()
    const input = await startEditing(user)
    await replaceName(user, input, '김철수')

    await user.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.getByLabelText('이름')).toBeDisabled())
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '취소' })).toBeDisabled()

    gate.release()

    expect(await screen.findByText('김철수')).toBeInTheDocument()
    expect(screen.queryByLabelText('이름')).not.toBeInTheDocument()
  })

  it('저장에 실패하면 서버의 오류 메시지를 안내하고, 편집 중인 상태와 입력한 이름을 유지한다', async () => {
    const user = userEvent.setup()
    server.use(http.patch(MY_INFO_URL, () => errorResponse(400, { detailMessage: '이미 사용 중인 이름입니다.' })))
    await renderProfile()
    const input = await startEditing(user)
    await replaceName(user, input, '김철수')

    await user.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('이미 사용 중인 이름입니다.'))
    expect(screen.getByLabelText('이름')).toHaveValue('김철수')
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
    expect(screen.queryByText('홍길동')).not.toBeInTheDocument()
  })
})

describe('마이페이지 - 회원 탈퇴', () => {
  const renderLoggedInPage = async () => {
    setAuthState('loggedIn')
    mockProductServer(makeProducts(1))
    const view = renderMyPage()
    await screen.findByText('홍길동')
    return view
  }

  it('탈퇴하기를 누르면 삭제되는 데이터를 알리는 확인 문구를 보여준다', async () => {
    const user = userEvent.setup()
    await renderLoggedInPage()

    await user.click(screen.getByRole('button', { name: '탈퇴하기' }))

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('정말 탈퇴할까요?'))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('지금까지 진단한 모든 상품과 진단 결과'))
  })

  it('확인을 취소하면 요청을 보내지 않고 로그인 상태도 그대로다', async () => {
    const user = userEvent.setup()
    vi.mocked(window.confirm).mockReturnValue(false)
    await renderLoggedInPage()

    await user.click(screen.getByRole('button', { name: '탈퇴하기' }))

    expect(requestLog.find('DELETE', '/api/v1/users/me')).toHaveLength(0)
    expect(useAuthStore.getState().isLoggedIn).toBe(true)
    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('탈퇴에 성공하면 메인으로 이동하고, 로그아웃하며 캐시를 비우고 완료를 안내한다', async () => {
    const user = userEvent.setup()
    const { queryClient } = await renderLoggedInPage()

    await user.click(screen.getByRole('button', { name: '탈퇴하기' }))

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/')
    expect(requestLog.find('DELETE', '/api/v1/users/me')).toHaveLength(1)
    expect(useAuthStore.getState()).toMatchObject({ isLoggedIn: false, accessToken: null })
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expect(window.alert).toHaveBeenCalledWith('탈퇴가 완료되었습니다. 그동안 팔기전에를 이용해주셔서 감사합니다.')
  })

  it('탈퇴하는 동안에는 버튼을 "탈퇴 중"으로 비활성화한다', async () => {
    const user = userEvent.setup()
    const gate = createGate()
    server.use(
      http.delete(MY_INFO_URL, async () => {
        await gate.promise
        return successResponse(null)
      }),
    )
    await renderLoggedInPage()

    await user.click(screen.getByRole('button', { name: '탈퇴하기' }))

    expect(await screen.findByRole('button', { name: '탈퇴 중' })).toBeDisabled()

    gate.release()

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
  })

  it('탈퇴에 실패하면 서버의 오류 메시지를 안내하고, 화면과 로그인 상태를 그대로 둔다', async () => {
    const user = userEvent.setup()
    server.use(http.delete(MY_INFO_URL, () => errorResponse(400, { detailMessage: '진행 중인 진단이 있어 탈퇴할 수 없습니다.' })))
    await renderLoggedInPage()

    await user.click(screen.getByRole('button', { name: '탈퇴하기' }))

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('진행 중인 진단이 있어 탈퇴할 수 없습니다.'))
    expect(getCurrentLocation()).toBe('/mypage')
    expect(useAuthStore.getState().isLoggedIn).toBe(true)
    expect(screen.getByRole('button', { name: '탈퇴하기' })).toBeEnabled()
  })
})
