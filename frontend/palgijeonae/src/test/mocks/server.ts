import { setupServer } from 'msw/node'

import { handlers } from './handlers'

// vitest.setup.ts에서 시작·초기화·종료한다. 테스트에서는 server.use(...)로 응답을 덮어쓴다.
export const server = setupServer(...handlers)
