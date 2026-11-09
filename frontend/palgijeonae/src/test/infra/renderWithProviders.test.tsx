import { useQuery } from '@tanstack/react-query'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { useAuthStore } from '@/store/useAuthStore'
import { authScenarios, setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderRoutes, renderWithProviders } from '@/test/utils/renderWithProviders'

function ParamsPage() {
  const { productId } = useParams<{ productId: string }>()
  const [searchParams] = useSearchParams()
  return <p>{`상품 ${productId} / 탭 ${searchParams.get('tab')}`}</p>
}

function NavigatePage() {
  const navigate = useNavigate()
  return <button onClick={() => navigate('/judgement/diagnoses-1')}>이동</button>
}

function BackPage() {
  const navigate = useNavigate()
  return <button onClick={() => navigate(-1)}>뒤로</button>
}

function FailingQueryPage() {
  const { isError, isPending } = useQuery({
    queryKey: ['always-fail'],
    queryFn: () => Promise.reject(new Error('실패')),
  })
  return <p>{isPending ? '불러오는 중' : isError ? '불러오지 못했어요' : '성공'}</p>
}

describe('renderWithProviders', () => {
  it('지정한 주소로 열고, 실제 라우터로 경로 파라미터와 쿼리를 읽는다', () => {
    renderWithProviders(<ParamsPage />, { path: '/question/:productId', route: '/question/product-1?tab=a' })

    expect(screen.getByText('상품 product-1 / 탭 a')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/question/product-1?tab=a')
  })

  it('useNavigate로 이동하면 extraRoutes의 도착 화면이 보이고 현재 주소가 바뀐다', async () => {
    renderWithProviders(<NavigatePage />, {
      path: '/question',
      route: '/question',
      extraRoutes: <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />,
    })

    await userEvent.click(screen.getByRole('button', { name: '이동' }))

    expect(screen.getByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-1')
  })

  it('history로 이전 항목을 깔아 두면 현재 주소는 route이고, navigate(-1)로 그 항목에 돌아간다', async () => {
    renderWithProviders(<BackPage />, {
      path: '/result',
      route: '/result',
      history: ['/mypage'],
      extraRoutes: <Route path="/mypage" element={<p>마이페이지 화면</p>} />,
    })
    expect(getCurrentLocation()).toBe('/result')

    await userEvent.click(screen.getByRole('button', { name: '뒤로' }))

    expect(screen.getByText('마이페이지 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('history를 주지 않으면 이전 항목이 없어서 navigate(-1)을 해도 주소가 그대로다', async () => {
    renderWithProviders(<BackPage />, { path: '/result', route: '/result' })

    await userEvent.click(screen.getByRole('button', { name: '뒤로' }))

    expect(getCurrentLocation()).toBe('/result')
  })

  it('QueryClient는 재시도하지 않아서 실패한 조회를 바로 확인할 수 있다', async () => {
    renderWithProviders(<FailingQueryPage />)

    // 재시도(기본 3회, 지수 대기)가 켜져 있다면 기본 대기 시간(1초) 안에 실패 화면이 나오지 않는다.
    expect(await screen.findByText('불러오지 못했어요')).toBeInTheDocument()
  })

  it('테스트마다 새 QueryClient를 쓰므로 이전 테스트의 캐시가 남지 않는다', () => {
    const { queryClient } = renderWithProviders(<p>화면</p>)

    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
  })
})

describe('renderRoutes', () => {
  it('중첩 Route 구성을 그대로 렌더한다', () => {
    renderRoutes(
      <Route element={<p>레이아웃</p>}>
        <Route path="/a" element={<p>A 화면</p>} />
      </Route>,
      { route: '/a' },
    )

    expect(screen.getByText('레이아웃')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/a')
  })
})

describe('인증 시나리오', () => {
  it.each(Object.keys(authScenarios) as (keyof typeof authScenarios)[])('%s 상태를 스토어에 설정한다', (scenario) => {
    setAuthState(scenario)

    const { isAuthReady, isLoggedIn, accessToken } = useAuthStore.getState()
    expect({ isAuthReady, isLoggedIn, accessToken }).toEqual(authScenarios[scenario])
  })

  it('로그인 상태로 설정한다', () => {
    setAuthState('loggedIn')

    expect(useAuthStore.getState().isLoggedIn).toBe(true)
  })

  it('다음 테스트에서는 인증 스토어가 초기 상태로 돌아가 있다', () => {
    expect(useAuthStore.getState()).toMatchObject({ isAuthReady: false, isLoggedIn: false, accessToken: null })
  })
})

describe('브라우저 API 스텁', () => {
  it('alert는 mock이라 호출 인자를 검증할 수 있다', () => {
    alert('질문에 모두 답변해 주세요.')

    expect(window.alert).toHaveBeenCalledWith('질문에 모두 답변해 주세요.')
  })

  it('scrollIntoView는 jsdom에 없으므로 mock으로 대신해서 호출해도 오류가 나지 않는다', () => {
    const element = document.createElement('div')

    element.scrollIntoView({ behavior: 'smooth' })

    expect(element.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })
  })

  it('alert 호출 기록은 테스트마다 초기화된다', async () => {
    await waitFor(() => expect(window.alert).not.toHaveBeenCalled())
  })
})
