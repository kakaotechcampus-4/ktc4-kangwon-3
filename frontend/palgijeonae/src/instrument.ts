import * as Sentry from '@sentry/react'
import { useEffect } from 'react'
import { createRoutesFromChildren, matchRoutes, useLocation, useNavigationType } from 'react-router-dom'

import { getUserIdFromAccessToken } from './lib/jwt'
import { useAuthStore } from './store/useAuthStore'

const dsn = import.meta.env.VITE_SENTRY_DSN

Sentry.init({
  dsn,
  environment: 'prod',
  // 프로덕션 빌드 + DSN 있을 때만 켠다
  enabled: import.meta.env.PROD && Boolean(dsn),
  // sendDefaultPii는 v11부터 deprecated라 dataCollection으로 대신 끈다
  dataCollection: {
    userInfo: false,
    cookies: false,
    httpHeaders: false,
    httpBodies: [],
  },
  integrations: [
    // 버전 고정 API 대신 버전 무관 API(v6~v8 공용) 사용
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

// JWT의 sub(BE userId)만 유저 컨텍스트로 남긴다
function syncSentryUser(accessToken: string | null) {
  const userId = accessToken ? getUserIdFromAccessToken(accessToken) : null
  Sentry.setUser(userId ? { id: userId } : null)
}

syncSentryUser(useAuthStore.getState().accessToken)

useAuthStore.subscribe((state, prevState) => {
  if (state.accessToken !== prevState.accessToken) {
    syncSentryUser(state.accessToken)
  }
})
