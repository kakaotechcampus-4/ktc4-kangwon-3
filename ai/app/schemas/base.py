"""모든 스키마가 공유하는 기본 모델과 UTC 시각 생성 함수."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


# 모델 생성 시마다 호출해 시간대 정보가 있는 UTC 시각을 만든다.
# 서버 지역 설정과 관계없이 시간을 비교할 수 있도록 사용한다.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 모든 스키마의 공통 부모. 정의하지 않은 필드는 오류로 처리해 오타·규격 불일치를 찾는다.
# extra="forbid"는 타입 변환까지 금지하는 strict=True 설정과는 다르다.
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# BE와 주고받는 API 경계 전용 부모 (#71, #171 §7.1.2). JSON은 camelCase, 파이썬 필드는 snake_case.
# 내부 StrictModel·LLM 스키마에는 쓰지 않음 (model_dump·json_schema 필드명까지 바뀜)
class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True,
        alias_generator=to_camel, populate_by_name=True,
    )


# BE가 보내는 요청 본문 전용. snake_case 키는 거부, camelCase만 허용
# ApiModel의 populate_by_name은 응답 모델을 코드에서 필드 이름으로 만들 때만 필요
class ApiRequestModel(ApiModel):
    model_config = ConfigDict(validate_by_name=False)
