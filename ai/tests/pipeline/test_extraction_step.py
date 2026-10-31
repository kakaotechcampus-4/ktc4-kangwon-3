"""진단 입력 → 상품 정보 추출 단계: 재진단 재사용, URL 수집, 실패 코드·재시도 여부를 가짜 추출기·가짜 수집기로 확인한다."""

import httpx
import openai
import pytest
from openai import LengthFinishReasonError
from openai.types.chat import ChatCompletion

from app.agents.base.meta import AgentRunMeta
from app.agents.extraction.errors import ExtractionFailedError
from app.agents.image_triage.errors import ImageTriageFailedError
from app.domain.context import PipelineStage
from app.domain.errors import AIResponseCode, AIServiceError
from app.pipeline.extraction_step import ExtractionStep
from app.pipeline.url_source import SiteConfig, UrlSourceBuilder
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.clients.marketplace_response import ProductPage, ProductPageImage
from app.schemas.product import Product
from app.schemas.session import DiagnosisInput

URL = "https://seller.en.made-in-china.com/product/AbCd/China-Power-Bank.html"


class _FakeExtractor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.inputs: list[ExtractionInput] = []

    def run(self, source: ExtractionInput) -> Product:
        self.inputs.append(source)
        if self.error is not None:
            raise self.error
        return Product(product_id=source.product_id, product_name="추출 결과")


class _FakeClient:
    def __init__(self, page: ProductPage | None = None, error: Exception | None = None) -> None:
        self.page = page
        self.error = error

    def fetch_parsed(self, request):
        if self.error is not None:
            raise self.error
        return self.page

    def close(self) -> None:
        pass


class _FailingTriage:
    def run(self, input):
        raise ImageTriageFailedError("이미지 분류 실패")


def _page(text_blocks: list[str], images: list[ProductPageImage] | None = None) -> ProductPage:
    return ProductPage(source_url=URL, site="made_in_china", title="보조배터리", text_blocks=text_blocks,
                       images=images or [])


def _builder(client: _FakeClient, images: str = "none", triage=None) -> UrlSourceBuilder:
    return UrlSourceBuilder(triage, sites={"made-in-china.com": SiteConfig(lambda: client, images=images)})


def _input(**source) -> DiagnosisInput:
    return DiagnosisInput(source=ExtractionInput(product_id="p-1", **source))


def _expect_failure(step: ExtractionStep, job_input: DiagnosisInput, code: AIResponseCode, retryable: bool) -> None:
    with pytest.raises(AIServiceError) as caught:
        step.run(job_input)
    assert caught.value.response_code is code.value
    assert caught.value.retryable is retryable
    assert caught.value.stage is PipelineStage.EXTRACTION


def test_재진단이면_이전_추출_결과를_쓰고_추출하지_않는다():
    previous = build_dummy_assessment("p-1")
    extractor = _FakeExtractor()
    step = ExtractionStep(extractor, _builder(_FakeClient(error=AssertionError("수집하면 안 됨"))))

    product = step.run(DiagnosisInput(source=ExtractionInput(product_id="p-1", source_url=URL), previous=previous))

    assert product == previous.product
    assert extractor.inputs == []


def test_글이_있으면_URL을_수집하지_않고_그대로_추출한다():
    extractor = _FakeExtractor()
    step = ExtractionStep(extractor, _builder(_FakeClient(error=AssertionError("수집하면 안 됨"))))
    job_input = _input(source_url=URL, text_blocks=["보조배터리 10000mAh"])

    product = step.run(job_input)

    assert extractor.inputs == [job_input.source]
    assert product.product_id == "p-1"


def test_긴_캡처_이미지는_조각으로_잘라_추출에_넘긴다():
    class _Splitter:
        def prepare(self, image_urls):
            return [f"{url}#조각{index}" for url in image_urls for index in range(2)]

    extractor = _FakeExtractor()
    step = ExtractionStep(extractor, _builder(_FakeClient()), image_splitter=_Splitter())

    step.run(_input(text_blocks=["충전기"], image_urls=["https://img/long.png"]))

    assert extractor.inputs[0].image_urls == ["https://img/long.png#조각0", "https://img/long.png#조각1"]
    assert extractor.inputs[0].text_blocks == ["충전기"]


def test_URL만_있으면_수집한_페이지로_추출한다():
    extractor = _FakeExtractor()
    step = ExtractionStep(extractor, _builder(_FakeClient(_page(["보조배터리", "Capacity: 10000mAh"]))))

    step.run(_input(source_url=URL))

    assert extractor.inputs == [ExtractionInput(product_id="p-1", source_url=URL,
                                                text_blocks=["보조배터리", "Capacity: 10000mAh"])]


def test_지원하지_않는_사이트면_재시도_불가로_실패한다():
    step = ExtractionStep(_FakeExtractor(), _builder(_FakeClient()))

    _expect_failure(step, _input(source_url="https://www.temu.com/kr/goods.html"),
                    AIResponseCode.UNSUPPORTED_SITE, retryable=False)


def test_페이지를_받지_못하면_재시도_가능으로_실패한다():
    error = httpx.ConnectError("연결 실패")
    step = ExtractionStep(_FakeExtractor(), _builder(_FakeClient(error=error)))

    _expect_failure(step, _input(source_url=URL), AIResponseCode.SOURCE_FETCH_FAILED, retryable=True)


def test_수집한_페이지에_글도_이미지도_없으면_재시도_불가로_실패한다():
    extractor = _FakeExtractor()
    step = ExtractionStep(extractor, _builder(_FakeClient(_page([]))))

    _expect_failure(step, _input(source_url=URL), AIResponseCode.EMPTY_SOURCE, retryable=False)
    assert extractor.inputs == []


def test_이미지_분류가_실패하면_재시도_가능으로_실패한다():
    image = ProductPageImage(url="https://img/spec.jpg", thumbnail_url="https://img/spec-small.jpg", area="description")
    builder = _builder(_FakeClient(_page(["보조배터리"], [image])), images="selected", triage=_FailingTriage())
    step = ExtractionStep(_FakeExtractor(), builder)

    _expect_failure(step, _input(source_url=URL), AIResponseCode.PIPELINE_ERROR, retryable=True)


def _status_error(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "https://llm.example/v1/chat/completions"))
    return openai.APIStatusError(f"HTTP {status}", response=response, body=None)


@pytest.mark.parametrize(("cause", "retryable"), [
    (_status_error(429), True),
    (_status_error(500), True),
    (_status_error(503), True),
    (openai.APIConnectionError(request=httpx.Request("POST", "https://llm.example")), True),
    (_status_error(400), False),
    (_status_error(401), False),
    (_status_error(404), False),
])
def test_모델_호출_실패는_429_5xx_연결_실패만_재시도_가능이다(cause, retryable):
    # 400·401·404는 요청·키·주소 오류라 같은 요청을 다시 보내도 실패함
    error = ExtractionFailedError("추출 실패", meta=AgentRunMeta(component="extraction", failure_phase="call"))
    error.__cause__ = cause
    step = ExtractionStep(_FakeExtractor(error), _builder(_FakeClient()))

    _expect_failure(step, _input(text_blocks=["보조배터리"]), AIResponseCode.PIPELINE_ERROR, retryable)


@pytest.mark.parametrize(("phase", "retryable"), [("call", True), ("parsing", False), ("finalize", False)])
def test_추출_모델_실패는_응답을_못_받았을_때만_재시도_가능이다(phase, retryable):
    error = ExtractionFailedError("추출 실패", meta=AgentRunMeta(component="extraction", failure_phase=phase))
    step = ExtractionStep(_FakeExtractor(error), _builder(_FakeClient()))

    _expect_failure(step, _input(text_blocks=["보조배터리"]), AIResponseCode.PIPELINE_ERROR, retryable)


def test_출력_길이_초과는_파싱_실패여도_재시도_가능이다():
    # 같은 내용을 반복하다 출력 한도에 닿는 실패. 같은 입력의 다른 회차는 정상이라 다시 하면 성공할 수 있음
    error = ExtractionFailedError("추출 실패", meta=AgentRunMeta(component="extraction", failure_phase="parsing"))
    error.__cause__ = LengthFinishReasonError(completion=ChatCompletion.model_construct(usage=None))
    step = ExtractionStep(_FakeExtractor(error), _builder(_FakeClient()))

    _expect_failure(step, _input(text_blocks=["보조배터리"]), AIResponseCode.PIPELINE_ERROR, retryable=True)
