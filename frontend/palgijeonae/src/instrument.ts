import * as Sentry from '@sentry/react'

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
})
