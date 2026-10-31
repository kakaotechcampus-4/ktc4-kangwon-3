"""진단 세션 실행 한도 (#264)."""

# 종료된 세션 보관 시간
SESSION_RETENTION_SECONDS = 3600
# 답변 대기 세션 보관 시간 (질문을 보낸 시각부터). 지나면 지워져 재진단은 404 → BE 실패 처리 (#301)
# 사용자가 답할 시간을 넉넉히 둠. 대기 세션은 원래 입력(이미지 포함)을 들고 있어 메모리와 맞바꿈
AWAITING_INPUT_RETENTION_SECONDS = 24 * 3600
# 동시 실행 상한. 넘는 세션은 대기
# 추출→선택 10개 동시 실측: 메모리 +58MB, 게이트웨이 거절·지연 없음. 외부 API 제한은 툴·클라이언트에서 따로
MAX_RUNNING_SESSIONS = 10
# 대기 + 실행 중 세션 상한. 넘으면 접수 거절
# t3.medium, AI 컨테이너 1GB 기준 최악 약 360MB (대기 세션당 약 5MB 추정)
MAX_INFLIGHT_SESSIONS = 50
# 샌드박스 진단 대기 + 실행 중 상한. 요청 하나(최대 10개)만큼, 운영 진단 자리를 덜 차지하게 따로 둠 (전체 상한에도 같이 셈)
MAX_DEV_INFLIGHT_SESSIONS = 10
# 접수부터 결과까지 최대 시간. 넘으면 시간 초과 실패
SESSION_MAX_DURATION_SECONDS = 600
# 시간 초과·보관 시간 정리 주기
SESSION_SWEEP_SECONDS = 30
