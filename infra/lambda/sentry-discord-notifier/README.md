# 개요

Sentry 새 이슈 알림을 프로젝트(BE·FE·AI)별 Discord 채널로 보내는 Lambda

Sentry 무료 플랜은 공식 Discord 통합을 쓸 수 없고, Sentry 웹훅 페이로드는 Discord 웹훅 형식(`content`/`embeds`)과 달라 바로 연결할 수 없습니다. 그래서 Lambda가 중간에서 형식을 바꿔 전달합니다.

## 구조

```
Sentry 알림 규칙 (프로젝트별, "새 이슈 생성")
   │  액션: 내부 통합 "Discord Notifier"
   ▼
Lambda `sentry` (ap-northeast-2, Function URL)
   │  Sentry-Hook-Signature 검증 → project id로 채널 선택 → Discord embed로 변환
   ▼
Discord 웹훅 ─ BE / FE / AI 채널
```

- 내부 통합은 조직에 1개, 알림 규칙은 프로젝트마다 1개, Lambda는 1개입니다.
- `event_alert`(알림 규칙에서 온 요청)만 Discord로 보냅니다. 내부 통합의 `issue` 등 다른 웹훅은 중복이라 200만 응답하고 버립니다.
- 알림 페이로드에는 프로젝트 slug가 없고 숫자 id(`data.event.project`)만 있어서, `index.mjs`의 `ROUTES`에서 id로 채널을 고릅니다.

## 파일

```
infra/lambda/sentry-discord-notifier/
├── index.mjs   # Lambda 핸들러
└── README.md
```

## Lambda 설정

| 항목 | 값 |
|---|---|
| 함수 이름 | `sentry` (ap-northeast-2) |
| 런타임 / 핸들러 | Node.js 24.x / `index.handler` (파일명은 `.mjs`) |
| 제한 시간 | 10초 (Discord 응답이 콜드스타트 때 2초 넘게 걸림) |
| 함수 URL | 인증 유형 `NONE` (요청 검증은 서명으로 함) |

환경변수 (값은 저장소에 두지 않습니다)

| 이름 | 값 |
|---|---|
| `CLIENT_SECRET` | 내부 통합 "Discord Notifier"의 Client Secret |
| `discord_webhook_be` | BE 채널 Discord 웹훅 URL |
| `discord_webhook_fe` | FE 채널 Discord 웹훅 URL |
| `discord_webhook_ai` | AI 채널 Discord 웹훅 URL |

## Sentry 설정

### 통합 설정 (조직에 1회)

1. Settings → Integrations → Custom Integrations → Create New Integration → **Internal Integration**
2. Webhook URL에 Lambda 함수 URL 입력 (Lambda 콘솔 → 구성 → 함수 URL)
3. **Alert Rule Action** 활성화
4. Save Changes
5. 저장 후 나오는 **Client Secret**을 Lambda 환경변수 `CLIENT_SECRET`에 넣습니다.

Webhooks 구독(issue 등)은 체크하지 않습니다. 체크해도 Lambda가 무시하지만 호출만 늘어납니다.

### 알림 설정 (프로젝트마다)

1. Monitors → Alerts → **Create Alert**
2. 프로젝트 선택
3. 조건은 **A new issue is created**만 남기고 나머지는 삭제
4. Select an action → **Send a notification via an integration** → Discord Notifier 선택
5. Create Alert

현재 규칙은 환경으로도 거릅니다: BE·FE `prod`, AI `production` (각 SDK의 environment 값과 같아야 합니다).

## 배포

```bash
cd infra/lambda/sentry-discord-notifier
zip -q function.zip index.mjs
aws lambda update-function-code --function-name sentry --zip-file fileb://function.zip
rm function.zip
```

## 프로젝트 추가

1. Discord 채널에서 웹훅 생성 → Lambda 환경변수 `discord_webhook_<이름>` 추가
2. `index.mjs`의 `ROUTES`에 `'<Sentry 프로젝트 id>': 'discord_webhook_<이름>'` 추가 후 배포
   - 프로젝트 id는 DSN 마지막 숫자 (`https://<key>@o....ingest.us.sentry.io/<프로젝트 id>`)
3. 위 "알림 설정"으로 그 프로젝트에 알림 규칙 생성

## 문제 확인

로그: `aws logs tail /aws/lambda/sentry --since 30m`

| 로그 | 의미 |
|---|---|
| 요청 기록 자체가 없음 | Sentry가 Lambda에 못 닿음 → 통합의 Webhook URL 확인 (Sentry 통합 화면의 Request Log에서 실제 전송 URL·응답 확인 가능) |
| 401 응답 | `CLIENT_SECRET`이 통합의 Client Secret과 다름 |
| `no route for project <id>` | `ROUTES`에 없는 프로젝트이거나 환경변수가 빠짐 |
| `discord <status> ...` | Discord가 거부함 → 웹훅 URL 확인 |

같은 메시지의 에러는 Sentry가 기존 이슈로 묶기 때문에 "새 이슈" 알림이 다시 오지 않습니다. 테스트할 때는 이벤트에 고유한 `fingerprint`를 넣어야 합니다. **알림이 실제 팀 채널로 가므로 테스트 이벤트는 꼭 필요할 때만 보냅니다.**
