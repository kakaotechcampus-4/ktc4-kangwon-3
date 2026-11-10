import { act, screen } from '@testing-library/react'
import { Route, useNavigationType, useParams } from 'react-router-dom'

import ProtectedRoute from '@/components/common/ProtectedRoute'
import { useAuthStore } from '@/store/useAuthStore'
import { requestLog } from '@/test/mocks/requestLog'
import { setAuthState } from '@/test/utils/auth'
import { getCurrentLocation, renderRoutes } from '@/test/utils/renderWithProviders'

// 이동이 history를 쌓았는지(PUSH) 덮어썼는지(REPLACE) 확인하려고 이동 방식을 화면에 보여준다.
function LoginStub() {
  const navigationType = useNavigationType()
  return (
    <>
      <p>로그인 화면</p>
      <p>{`이동 방식: ${navigationType}`}</p>
    </>
  )
}

function QuestionStub() {
  const { productId } = useParams<{ productId: string }>()
  return <p>{`질문 화면 ${productId}`}</p>
}

// App.tsx와 같은 구조: 로그인 화면은 공개이고, 나머지는 ProtectedRoute 아래의 중첩 Route다.
const renderGuardedRoutes = (route: string) =>
  renderRoutes(
    <>
      <Route path="/login" element={<LoginStub />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/upload" element={<p>업로드 화면</p>} />
        <Route path="/products" element={<p>진단 결과 화면</p>} />
        <Route path="/mypage" element={<p>마이페이지 화면</p>} />
        <Route path="/question/:productId" element={<QuestionStub />} />
      </Route>
    </>,
    { route },
  )

describe('보호 라우트 - 인증 준비 전', () => {
  beforeEach(() => {
    setAuthState('restoring')
  })

  it('세션 복구가 끝나기 전에는 보호된 화면도 로그인 화면도 보여주지 않고 기다린다', () => {
    renderGuardedRoutes('/upload')

    expect(screen.queryByText('업로드 화면')).not.toBeInTheDocument()
    expect(screen.queryByText('로그인 화면')).not.toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/upload')
  })

  it('기다리는 동안에는 로그인 화면으로 리다이렉트하지 않는다 (새로고침 직후 깜빡임 방지)', () => {
    renderGuardedRoutes('/mypage')

    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('isLoggedIn이 true여도 인증 준비가 끝나기 전에는 기다린다', () => {
    useAuthStore.setState({ isAuthReady: false, isLoggedIn: true })
    renderGuardedRoutes('/upload')

    expect(screen.queryByText('업로드 화면')).not.toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/upload')
  })

  it('기다리다가 세션 복구에 성공하면 보호된 화면을 보여준다', async () => {
    renderGuardedRoutes('/upload')
    expect(screen.queryByText('업로드 화면')).not.toBeInTheDocument()

    act(() => useAuthStore.getState().login('restored-token'))

    expect(await screen.findByText('업로드 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/upload')
  })

  it('기다리다가 세션 복구에 실패하면 로그인 화면으로 보낸다', async () => {
    renderGuardedRoutes('/upload')

    act(() => useAuthStore.getState().logout())

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/login')
  })

  it('공개 화면(로그인)은 인증 준비 전에도 바로 보인다', () => {
    renderGuardedRoutes('/login')

    expect(screen.getByText('로그인 화면')).toBeInTheDocument()
  })
})

describe('보호 라우트 - 비로그인', () => {
  beforeEach(() => {
    setAuthState('loggedOut')
  })

  it.each(['/upload', '/products', '/mypage', '/question/product-1'])('%s에 접근하면 로그인 화면으로 리다이렉트한다', (path) => {
    renderGuardedRoutes(path)

    expect(screen.getByText('로그인 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/login')
  })

  it('보호된 화면은 한 번도 렌더하지 않는다', () => {
    renderGuardedRoutes('/question/product-1')

    expect(screen.queryByText(/질문 화면/)).not.toBeInTheDocument()
  })

  it('리다이렉트는 history를 쌓지 않고 덮어쓴다 (뒤로가기로 보호된 화면에 되돌아오지 않게)', () => {
    renderGuardedRoutes('/upload')

    expect(screen.getByText('이동 방식: REPLACE')).toBeInTheDocument()
  })

  it('공개 화면(로그인)에는 그대로 접근할 수 있다', () => {
    renderGuardedRoutes('/login')

    expect(screen.getByText('로그인 화면')).toBeInTheDocument()
    expect(screen.getByText('이동 방식: POP')).toBeInTheDocument()
  })
})

describe('보호 라우트 - 로그인 상태', () => {
  beforeEach(() => {
    setAuthState('loggedIn')
  })

  it.each([
    ['/upload', '업로드 화면'],
    ['/mypage', '마이페이지 화면'],
  ])('%s에 접근하면 보호된 화면을 보여주고 주소를 바꾸지 않는다', (path, screenText) => {
    renderGuardedRoutes(path)

    expect(screen.getByText(screenText)).toBeInTheDocument()
    expect(screen.queryByText('로그인 화면')).not.toBeInTheDocument()
    expect(getCurrentLocation()).toBe(path)
  })

  it('중첩 라우트의 경로 파라미터를 화면까지 전달한다', () => {
    renderGuardedRoutes('/question/product-1')

    expect(screen.getByText('질문 화면 product-1')).toBeInTheDocument()
  })

  it('화면을 보고 있다가 로그아웃되면 로그인 화면으로 보낸다', async () => {
    renderGuardedRoutes('/mypage')
    expect(screen.getByText('마이페이지 화면')).toBeInTheDocument()

    act(() => useAuthStore.getState().logout())

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
    expect(screen.queryByText('마이페이지 화면')).not.toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/login')
  })

  it('공개 화면(로그인)도 그대로 접근할 수 있다 (로그인 상태라고 막지 않는다)', () => {
    renderGuardedRoutes('/login')

    expect(screen.getByText('로그인 화면')).toBeInTheDocument()
  })
})

describe('보호 라우트 - 네트워크', () => {
  it.each(['restoring', 'loggedOut', 'loggedIn'] as const)('%s 상태에서도 가드 자체는 API를 호출하지 않는다 (세션 복구는 App의 역할)', (scenario) => {
    setAuthState(scenario)
    renderGuardedRoutes('/upload')

    expect(requestLog.all()).toEqual([])
  })
})
