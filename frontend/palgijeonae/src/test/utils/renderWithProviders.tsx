import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { type InitialEntry, MemoryRouter, Route, Routes } from 'react-router-dom'

import LocationDisplay from './LocationDisplay'

// 실패한 요청을 재시도하면 테스트가 느려지고 실패 화면을 바로 확인할 수 없으므로 재시도를 끈다.
export const createTestQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

export const getCurrentLocation = (): string | null => screen.getByTestId('location').textContent

interface RenderOptions {
  // 처음 열려 있는 주소. 예: '/question/product-1'
  // 다른 화면이 navigate state로 넘겨주는 값이 필요하면 객체로 준다. 예: { pathname: '/upload', state: { demoProducts } }
  route?: InitialEntry
  queryClient?: QueryClient
}

// 실제 라우터 컨텍스트(MemoryRouter)와 QueryClient 안에 <Route> 구성을 그대로 렌더한다. 보호 라우트처럼 중첩 Route가 필요할 때 쓴다.
export function renderRoutes(routes: ReactNode, { route = '/', queryClient = createTestQueryClient() }: RenderOptions = {}) {
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>{routes}</Routes>
        <LocationDisplay />
      </MemoryRouter>
    </QueryClientProvider>,
  )

  return { ...result, queryClient }
}

interface RenderWithProvidersOptions extends RenderOptions {
  // ui를 붙일 Route 경로 패턴. 파라미터가 필요하면 지정한다. 예: '/question/:productId'
  path?: string
  // 화면 이동 결과를 확인할 도착 화면들. 예: <Route path="/judgement/:diagnosesId" element={<div>진단 중</div>} />
  extraRoutes?: ReactNode
}

// 화면 하나를 라우터·QueryClient와 함께 렌더한다. useNavigate/useLocation/useParams는 모킹하지 않고 실제 라우터로 동작한다.
export function renderWithProviders(ui: ReactElement, { path = '*', extraRoutes, ...options }: RenderWithProvidersOptions = {}) {
  return renderRoutes(
    <>
      <Route path={path} element={ui} />
      {extraRoutes}
    </>,
    options,
  )
}
