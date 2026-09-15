## S3 temp/ Lifecycle Rule 설정 (고아 파일 자동 정리)

클라이언트는 presigned URL을 통해 `temp/` 경로로 파일을 먼저 업로드하고, 진단서 생성 API 호출이 성공해야만 서버가 이를 정식 경로(`product-main/`, `product-detail/` 등)로 옮깁니다. 업로드는 됐지만 네트워크 오류나 이탈로 진단서 생성 API가 호출되지 않으면 `temp/` 아래에 파일이 영구적으로 남을 수 있습니다.

잔존 파일은 애플리케이션 코드가 아니라 **S3 버킷의 Lifecycle Rule**로 자동 정리시킵니다.

### 설정 절차 (AWS 콘솔)

1. S3 콘솔 → 대상 버킷 선택 → **관리(Management)** 탭 → **수명 주기 규칙(Lifecycle rules)** → **수명 주기 규칙 생성(Create lifecycle rule)**.
2. 규칙 범위: "규칙 범위를 하나 이상의 필터로 제한"을 선택하고, **접두사(Prefix)**에 `temp/` 입력.
3. 수명 주기 규칙 작업: "객체의 현재 버전 만료(Expire current versions of objects)" 체크.
4. 객체 생성 후 일수: `1` (24시간 이후 만료).
5. 버전 관리(Versioning)가 켜져 있는 버킷이라면 "이전 버전 영구 삭제(Permanently delete previous versions of objects)"도 함께 설정해 비용이 누적되지 않도록 합니다.
6. 규칙 생성 후 저장.

### 설정 절차 (AWS CLI, 콘솔 대안)

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket <버킷명> \
  --lifecycle-configuration '{
    "Rules": [
      {
        "ID": "temp-orphan-file-expiration",
        "Filter": { "Prefix": "temp/" },
        "Status": "Enabled",
        "Expiration": { "Days": 1 }
      }
    ]
  }'
```

### 확인 방법

```bash
aws s3api get-bucket-lifecycle-configuration --bucket <버킷명>
```

`temp/` prefix에 `Expiration.Days: 1` 규칙이 조회되면 정상 적용된 것입니다. S3 Lifecycle은 매일 1회 배치로 평가되므로, 실제 삭제는 만료 시각 이후 최대 24시간 이내에 이뤄질 수 있습니다(즉시 삭제 보장 아님).