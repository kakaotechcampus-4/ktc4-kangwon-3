"""모든 스키마가 공유하는 기본 모델과 UTC 시각 생성 함수."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


# 모델 생성 시마다 호출해 시간대 정보가 있는 UTC 시각을 만든다.
# 서버 지역 설정과 관계없이 시간을 비교할 수 있도록 사용한다.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 모든 스키마의 공통 부모. 정의하지 않은 필드는 오류로 처리해 오타·규격 불일치를 찾는다.
# extra="forbid"는 타입 변환까지 금지하는 strict=True 설정과는 다르다.
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
