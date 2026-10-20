"""진단 세션 실행 한도 (#264)."""

# 종료된 세션 보관 시간, 답변 대기 세션은 삭제하지 않음
SESSION_RETENTION_SECONDS = 3600
# 동시 실행 상한. 넘는 세션은 대기
# 추출→선택 10개 동시 실측: 메모리 +58MB, 게이트웨이 거절·지연 없음. 외부 API 제한은 툴·클라이언트에서 따로
MAX_RUNNING_SESSIONS = 10
# 대기 + 실행 중 세션 상한. 넘으면 접수 거절
# t3.medium, AI 컨테이너 1GB 기준 최악 약 360MB (대기 세션당 약 5MB 추정)
MAX_INFLIGHT_SESSIONS = 50
# 개발용 진단(/dev) 대기 + 실행 중 상한. 운영 진단 자리를 덜 차지하게 따로 작게 (전체 상한에도 같이 셈)
MAX_DEV_INFLIGHT_SESSIONS = 3
# 접수부터 결과까지 최대 시간. 넘으면 시간 초과 실패
SESSION_MAX_DURATION_SECONDS = 600
# 시간 초과·보관 시간 정리 주기
SESSION_SWEEP_SECONDS = 30
