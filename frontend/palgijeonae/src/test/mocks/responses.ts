import { HttpResponse } from 'msw'

// 서버의 성공 응답 형태({ data })를 만든다. 오버라이드 핸들러에서 쓴다.
export const successResponse = (data: unknown, status = 200) => HttpResponse.json({ data }, { status })

// S3는 앱과 출처가 달라서, jsdom XHR이 응답을 받아들이려면 CORS 헤더가 필요하다. (실제 버킷도 CORS 설정이 필요하다)
export const S3_CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'PUT, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

// S3 업로드 응답. 실패 시나리오는 s3Response(403)처럼 상태 코드만 바꿔서 server.use로 덮어쓴다.
export const s3Response = (status = 200) => new HttpResponse(null, { status, headers: S3_CORS_HEADERS })

interface ErrorResponseBody {
  code?: string
  message?: string
  // getErrorMessage가 우선해서 보여주는 상세 메시지
  detailMessage?: string
  headers?: Record<string, string>
}

// 서버의 에러 응답 형태({ code, message, details })를 만든다. 예: errorResponse(400, { code: 'COMMON-001', message: '...' })
export const errorResponse = (status: number, { code = 'COMMON-001', message = '요청에 실패했습니다.', detailMessage, headers }: ErrorResponseBody = {}) =>
  HttpResponse.json(
    { code, message, ...(detailMessage ? { details: [{ message: detailMessage }] } : {}) },
    { status, headers },
  )
