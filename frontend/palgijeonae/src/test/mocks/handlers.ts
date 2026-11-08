import { http } from 'msw'

import type { PresignedFile } from '@/api/uploads'

import { buildDiagnosesDetail, buildMyProduct, buildProductResult, buildUserInfo } from './fixtures'
import { recordRequest } from './requestLog'
import { s3Response, successResponse } from './responses'

// apiClient가 쓰는 주소. vite.config.ts의 test.env로 고정하며, 빈 값이면 `/api/...`처럼 jsdom과 같은 출처로 요청한다.
export const API_URL = import.meta.env.VITE_API_URL as string
export const S3_URL = 'https://s3.test.local'
export const DEFAULT_DIAGNOSES_ID = 'diagnoses-test-id'

interface PresignedRequestBody {
  files: { type: string; fileName: string; fileSize: number }[]
}

// 모든 테스트에서 기본으로 쓰는 "성공" 핸들러. 실패 응답이나 다른 데이터는 테스트에서 server.use(...)로 덮어쓴다.
export const handlers = [
  // presigned URL 발급: 요청한 파일 순서대로 key를 만들어 돌려준다.
  http.post(`${API_URL}/api/v1/presigned-url`, async ({ request }) => {
    const { files } = await recordRequest<PresignedRequestBody>(request)
    const presignedFiles: PresignedFile[] = files.map((file, index) => {
      const key = `uploads/${index}-${file.fileName}`
      return { fileName: file.fileName, key, presignedUrl: `${S3_URL}/${key}`, contentType: 'image/png' }
    })
    return successResponse({ files: presignedFiles })
  }),

  // S3 업로드(PUT). 출처가 달라 브라우저가 보내는 사전 요청(OPTIONS)에도 응답한다.
  http.options(`${S3_URL}/*`, () => s3Response(204)),
  http.put(`${S3_URL}/*`, async ({ request }) => {
    await recordRequest(request)
    return s3Response()
  }),

  // 진단 제출
  http.post(`${API_URL}/api/v1/diagnoses`, async ({ request }) => {
    await recordRequest(request)
    return successResponse({ diagnosesId: DEFAULT_DIAGNOSES_ID })
  }),

  // 질문 화면이 읽는 상품 단건 조회: 답변 대기 중인 상품과 질문 하나
  http.get(`${API_URL}/api/v1/products/:productId`, async ({ request, params }) => {
    await recordRequest(request)
    return successResponse(buildProductResult({ productId: String(params.productId) }))
  }),

  // 질문 답변 제출
  http.post(`${API_URL}/api/v1/products/:productId/answers`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(null)
  }),

  // 진단 진행 화면(폴링)·진단서 결과 조회: 진행 중인 상품 하나, 폴링 없음
  http.get(`${API_URL}/api/v1/diagnoses/:diagnosesId`, async ({ request, params }) => {
    await recordRequest(request)
    return successResponse(buildDiagnosesDetail({ diagnosesId: String(params.diagnosesId) }))
  }),

  // 실패한 상품 재진단
  http.post(`${API_URL}/api/v1/products/:productId/retry`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(null)
  }),

  // 마이페이지 상품 목록: 상품 하나, 한 페이지. 검색·필터·페이지 동작은 테스트에서 server.use로 덮어써서 확인한다.
  http.get(`${API_URL}/api/v1/products`, async ({ request }) => {
    await recordRequest(request)
    return successResponse({
      products: [buildMyProduct()],
      pageInfo: { page: 0, size: 10, totalElements: 1, totalPages: 1, hasNext: false },
    })
  }),

  // 마이페이지 상품 삭제
  http.delete(`${API_URL}/api/v1/products/:productId`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(null)
  }),

  // 법령 개정 알림 조회: 기본은 빈 목록(배너 없음)
  http.get(`${API_URL}/api/v1/law-amendments`, async ({ request }) => {
    await recordRequest(request)
    return successResponse({ lawAmendments: [] })
  }),

  // 진단을 마친 상품 재진단
  http.post(`${API_URL}/api/v1/products/:productId/rediagnosis`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(null)
  }),

  // 알림 설정 조회·수정: 기본은 켜짐. 수정은 요청 본문을 그대로 돌려준다.
  http.get(`${API_URL}/api/v1/users/me/notification-settings`, async ({ request }) => {
    await recordRequest(request)
    return successResponse({ lawAmendmentAlertEnabled: true })
  }),
  http.patch(`${API_URL}/api/v1/users/me/notification-settings`, async ({ request }) => {
    const { lawAmendmentAlertEnabled } = await recordRequest<{ lawAmendmentAlertEnabled: boolean }>(request)
    return successResponse({ lawAmendmentAlertEnabled })
  }),

  // 회원 정보 조회·이름 수정·탈퇴
  http.get(`${API_URL}/api/v1/users/me`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(buildUserInfo())
  }),
  http.patch(`${API_URL}/api/v1/users/me`, async ({ request }) => {
    const { name } = await recordRequest<{ name: string }>(request)
    return successResponse(buildUserInfo({ name }))
  }),
  http.delete(`${API_URL}/api/v1/users/me`, async ({ request }) => {
    await recordRequest(request)
    return successResponse(null)
  }),
]
