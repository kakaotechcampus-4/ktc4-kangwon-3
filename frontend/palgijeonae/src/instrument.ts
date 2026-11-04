import * as Sentry from '@sentry/react'
import { useEffect } from 'react'
import { createRoutesFromChildren, matchRoutes, useLocation, useNavigationType } from 'react-router-dom'

import { getUserIdFromAccessToken } from './lib/jwt'
import { useAuthStore } from './store/useAuthStore'

const dsn = import.meta.env.VITE_SENTRY_DSN

Sentry.init({
  dsn,
  environment: 'prod',
  // 프로덕션 빌드(vite build)에서 DSN이 있을 때만 켠다. 로컬 dev 서버(vite)에서는 PROD가 false라 꺼진다.
  enabled: import.meta.env.PROD && Boolean(dsn),
  // sendDefaultPii는 SDK v11부터 deprecated(항상 dataCollection 기본값이 적용됨)라,
  // 토큰·이메일·요청 본문을 보내지 않으려면 dataCollection 항목을 직접 꺼야 한다.
  dataCollection: {
    userInfo: false,
    cookies: false,
    httpHeaders: false,
    httpBodies: [],
  },
  integrations: [
    // v7 전용 reactRouterV7BrowserTracingIntegration 대신, SDK 10.59.0+에서 쓸 수 있는
    // 버전 무관 API(v6·v7·v8 공용)를 쓴다.
    Sentry.reactRouterBrowserTracingIntegration({
      useEffect,
      useLocation,
      useNavigationType,
      createRoutesFromChildren,
      matchRoutes,
    }),
  ],
  tracesSampleRate: 0.2,
})

// accessToken(JWT)의 sub(BE userId)를 유저 컨텍스트로 남긴다.
function syncSentryUser(accessToken: string | null) {
  const userId = accessToken ? getUserIdFromAccessToken(accessToken) : null
  Sentry.setUser(userId ? { id: userId } : null)
}

syncSentryUser(useAuthStore.getState().accessToken)

useAuthStore.subscribe((state, prevState) => {
  // login(최초 로그인·재발급)과 logout 모두 accessToken이 바뀌므로 이 변화만 보면 된다.
  if (state.accessToken !== prevState.accessToken) {
    syncSentryUser(state.accessToken)
  }
})
