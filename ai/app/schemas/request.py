"""진단 엔드포인트 요청 스키마."""

from pydantic import Field, model_validator

from .base import ApiRequestModel


class DiagnosisProductInput(ApiRequestModel):
    """진단서에 담긴 상품 하나. 텍스트·이미지·URL 중 하나 이상 필수 (#371).

    Args:
        product_id: BE 상품 ID (UUID v7). 세션 ID로 사용.
        text_blocks: 상품 상세페이지에서 복사한 텍스트 블록 목록.
        image_urls: 이미지 URL 목록. base64 data URI도 받음 (#389).
        source_url: 상품 페이지 URL. 텍스트·이미지가 있으면 출처 표시용, 없으면 수집 대상.
    """

    product_id: str = Field(min_length=1)
    text_blocks: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    source_url: str | None = None

    @model_validator(mode="after")
    def at_least_one_input(self):
        if not self.text_blocks and not self.image_urls and not self.source_url:
            raise ValueError("textBlocks, imageUrls, sourceUrl 중 하나는 필수입니다.")
        return self


class DiagnosisRequest(ApiRequestModel):
    """진단서 한 건의 상품들을 한 번에 접수하는 요청 (#263).

    Args:
        diagnosis_id: BE 진단서 ID.
        products: 진단할 상품 목록. 1~10개, productId 중복 불가.
    """

    diagnosis_id: str = Field(min_length=1)
    # 이미지 base64가 본문에 들어가 요청 크기 제한용 상한
    products: list[DiagnosisProductInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_product_ids(self):
        ids = [product.product_id for product in self.products]
        duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
        if duplicates:
            raise ValueError(f"productId가 중복됩니다: {', '.join(duplicates)}")
        return self


class AnswerInput(ApiRequestModel):
    """질문 하나에 대한 사용자 답변.

    Args:
        question_key: 질문 콜백으로 보낸 질문 키 (BE ProductQuestion.questionKey).
        answer_text: 사용자 답변. 최대 500자 (BE 답변 제출 API와 같은 기준).
    """

    question_key: str = Field(min_length=1, max_length=50)
    # 사용자가 직접 입력한 글이 LLM 입력으로 들어감. 길이·공백 외 검사는 답변 세이프가드에서
    answer_text: str = Field(min_length=1, max_length=500, pattern=r"\S")


class ResumeRequest(ApiRequestModel):
    """답변 대기 상품을 사용자 답변으로 이어서 진단하는 요청 (#310).

    원래 입력·추출 결과·이전 질문과 답변은 AI 세션이 보관. BE는 ID와 이번 회차 답변만 보냄.

    Args:
        diagnosis_id: BE 진단서 ID.
        product_id: BE 상품 ID (세션 ID).
        run_id: 질문으로 끝난 실행 ID. 중복·늦게 온 답변 구분용.
        question_round: 답하는 질문 회차. 1~2.
        answers: 이번 회차 답변. questionKey 중복 불가.
    """

    diagnosis_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_round: int = Field(ge=1, le=2, strict=True)
    answers: list[AnswerInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_question_keys(self):
        keys = [answer.question_key for answer in self.answers]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"questionKey가 중복됩니다: {', '.join(duplicates)}")
        return self


class DevDiagnosisProductInput(ApiRequestModel):
    """샌드박스 진단 상품 하나. 텍스트·이미지·URL 중 하나 이상 필수 (#371). 상품 ID는 서버가 발급.

    이미지는 #310 합의대로 URL로 받음(base64 data URI도 호환).

    Args:
        text_blocks: 상품 상세페이지에서 복사한 텍스트 블록 목록.
        image_urls: 이미지 URL 목록 (base64 data URI도 받음).
        source_url: 상품 페이지 URL. 텍스트·이미지가 있으면 출처 표시용, 없으면 수집 대상.
    """

    text_blocks: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    source_url: str | None = None

    @model_validator(mode="after")
    def at_least_one_input(self):
        if not self.text_blocks and not self.image_urls and not self.source_url:
            raise ValueError("textBlocks, imageUrls, sourceUrl 중 하나는 필수입니다.")
        return self


class DevDiagnosisRequest(ApiRequestModel):
    """샌드박스 진단 요청 (#318). 실제 진단 접수처럼 상품을 목록으로 받음.

    Args:
        products: 진단할 상품 목록. 1~10개.
    """

    products: list[DevDiagnosisProductInput] = Field(min_length=1, max_length=10)
