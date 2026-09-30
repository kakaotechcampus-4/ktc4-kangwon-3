"""AI 서버 전용 Prometheus 지표 정의.

HTTP 요청 지표는 main.py의 Instrumentator가 수집하고, 여기에는 AI 서버 고유 지표만 둔다.
라벨에는 상품 ID, URL, 검색어처럼 값이 계속 늘어나는 항목을 넣지 않는다.
"""

from prometheus_client import Counter, Histogram

# SafetyKorea 응답이 96초까지 걸린 사례 있음
EXTERNAL_API_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)

EXTERNAL_API_REQUESTS = Counter(
    "ai_external_api_requests_total",
    "외부 API 호출 수",
    ["client", "result"],
)

EXTERNAL_API_DURATION = Histogram(
    "ai_external_api_request_duration_seconds",
    "외부 API 호출 소요시간 (응답 본문 수신 포함)",
    ["client"],
    buckets=EXTERNAL_API_LATENCY_BUCKETS,
)

LLM_LATENCY_BUCKETS = (0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)

LLM_REQUESTS = Counter(
    "ai_llm_requests_total",
    "LLM 호출 수",
    ["agent", "model", "result"],
)

LLM_DURATION = Histogram(
    "ai_llm_request_duration_seconds",
    "LLM 호출 소요시간",
    ["agent"],
    buckets=LLM_LATENCY_BUCKETS,
)

LLM_TOKENS = Counter(
    "ai_llm_tokens_total",
    "LLM 토큰 사용량 (type: uncached, cached, output)",
    ["agent", "model", "type"],
)

LLM_COST_KRW = Counter(
    "ai_llm_cost_krw_total",
    "LLM 추정 비용 (KRW)",
    ["agent", "model"],
)
