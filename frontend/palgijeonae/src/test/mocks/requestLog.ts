// MSW 핸들러가 받은 요청을 기록해서, 테스트에서 "무엇을 보냈는지"(경로·헤더·본문)를 검증할 수 있게 한다.
// 핸들러가 응답하기 전에 기록하므로, 화면이 응답을 받은 시점에는 이미 기록되어 있다.
export interface RecordedRequest {
  method: string
  url: string
  pathname: string
  headers: Headers
  // JSON 요청은 파싱한 값, 그 외(S3 업로드의 파일 등)는 Blob, 본문이 없으면 undefined
  body: unknown
}

const recorded: RecordedRequest[] = []

export const requestLog = {
  all: (): RecordedRequest[] => [...recorded],

  // 메서드와 경로(pathname)가 일치하는 요청들을 보낸 순서대로 돌려준다. 예: requestLog.find('POST', '/api/v1/diagnoses')
  find: (method: string, pathname: string): RecordedRequest[] =>
    recorded.filter((entry) => entry.method === method.toUpperCase() && entry.pathname === pathname),

  clear: (): void => {
    recorded.length = 0
  },
}

// 요청을 기록하고, JSON 본문이면 파싱한 값을 돌려준다. 기본 핸들러와 테스트의 오버라이드 핸들러가 함께 쓴다.
export async function recordRequest<TBody = unknown>(request: Request): Promise<TBody> {
  const clone = request.clone()
  const contentType = request.headers.get('content-type') ?? ''
  const hasBody = !['GET', 'HEAD'].includes(request.method)

  let body: unknown
  if (hasBody) {
    body = contentType.includes('application/json') ? await clone.json() : await clone.blob()
  }

  recorded.push({
    method: request.method,
    url: request.url,
    pathname: new URL(request.url).pathname,
    headers: request.headers,
    body,
  })

  return body as TBody
}
