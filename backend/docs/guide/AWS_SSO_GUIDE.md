## AWS SSO 로그인 (S3 Presigned URL 기능)

이 계정은 조직 정책상 IAM 사용자/액세스 키 생성이 막혀 있어, S3 자격증명은 **AWS SDK의 `DefaultCredentialsProvider`**가 자동으로 찾는 방식을 사용합니다.

- **로컬 개발**: 각자 AWS SSO 세션으로 자격증명을 받습니다.
- **운영(EC2)**: 인스턴스에 붙은 IAM Role을 그대로 쓰므로 별도 설정이 불필요합니다.

로컬에서 매번 해줘야 하는 것:

```bash
# 자세한 설정 방법은 카테캠 노션 AWS 사용 가이드 3번을 참조해주세요.
# 1. 최초 1회 (또는 세션 만료 시)
aws sso login --profile <본인 SSO 프로필명>
# 예: aws sso login --profile StudentDeveloper-123456789
# --profile을 안 붙이면 CLI가 "default"라는 이름의 프로필을 찾는데,
# ~/.aws/config에 그 이름의 프로필이 없으면 에러가 납니다.
# (본인 프로필명은 `cat ~/.aws/config`의 [profile ...] 섹션 참고)
# (default로 해두면 편하지만 다른 aws 프로필과 혼동 주의)

# 2. 앱이 같은 프로필을 쓰도록 지정 (또는 .env에 저장)
export AWS_PROFILE=<본인 SSO 프로필명>
```

- SSO 세션은 1시간 이후 만료되며, `aws sso login --profile <프로필명>` 명령어로 다시 갱신할 수 있습니다.
- `InvalidGrantException`이 발생하면 캐시된 SSO 토큰이 꼬인 것이니 `rm -rf ~/.aws/sso/cache/*` 후 `aws sso login`을 다시 하면 대부분 해결됩니다.
