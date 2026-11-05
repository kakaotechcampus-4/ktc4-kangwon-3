export type SentryLevel = 'error' | 'warning'

const ERROR_CODES = new Set(['COMMON-001', 'COMMON-002', 'COMMON-007', 'AUTH-005'])

const WARNING_CODES = new Set(['FILE-001', 'FILE-003', 'COMMON-003', 'COMMON-005', 'COMMON-006', 'AUTH-004'])

// 재발급 후 재시도한 요청에서 또 발생했을 때만 warning으로 보낸다 (최초 1회는 토큰 재발급으로 자연 복구될 수 있어 제외)
const WARNING_IF_RETRIED_CODES = new Set(['AUTH-002', 'COMMON-004'])

const SILENT_CODES = new Set(['AUTH-001', 'AUTH-003', 'COMMON-009', 'COMMON-010', 'COMMON-011'])

interface ApiErrorClassifyInput {
    status?: number
    code?: string
    retried: boolean
}

// BE 에러 코드를 우선 기준으로 판단하고, 코드가 없거나 알 수 없는 코드일 때만 상태코드로 판단한다.
export function classifyApiError({ status, code, retried }: ApiErrorClassifyInput): SentryLevel | null {
    if (code) {
        if (SILENT_CODES.has(code)) {
            return null
        }
        if (ERROR_CODES.has(code)) {
            return 'error'
        }
        if (WARNING_CODES.has(code)) {
            return 'warning'
        }
        if (WARNING_IF_RETRIED_CODES.has(code)) {
            return retried ? 'warning' : null
        }
    }

    if (!status) {
        return 'error'
    }
    return status >= 500 ? 'error' : null
}

// UUID 형태의 경로 구간
const UUID_SEGMENT_PATTERN = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i

// 같은 엔드포인트에서 난 에러를 하나의 이슈로 묶기 위해 쿼리스트링을 떼고 UUID id 구간을 :id로 치환한다.
export function toPathTemplate(url: string): string {
    return url
        .split('?')[0]
        .split('/')
        .map((segment) => (UUID_SEGMENT_PATTERN.test(segment) ? ':id' : segment))
        .join('/')
}
