"""ImageTriageAgent 입출력: [n] 번호 블록, 번호순 결과, 입력에 없는 번호 거부, 호출 안 하는 경우 (#337)."""

import json

import pytest

from app.agents.image_triage import MAX_IMAGES, ImageTriageAgent, ImageTriageFailedError, ImageTriageInput
from app.config import AGENT_PROFILES
from app.schemas.agent import ImageCategory

URLS = [f"https://image.made-in-china.com/202f0j00Photo{n}/Power-Bank.webp" for n in (1, 2, 3)]


def _answer(*items: tuple[int, str]) -> str:
    return json.dumps({"items": [{"index": index, "category": category} for index, category in items]})


def _input(urls: list[str] = URLS) -> ImageTriageInput:
    return ImageTriageInput(image_urls=urls, subject_id="page-1")


def test_이미지마다_번호를_붙여_순서대로_보낸다(fake_gateway, records):
    requests: list[dict] = []
    agent = ImageTriageAgent(fake_gateway(_answer((1, "product"), (2, "specification"), (3, "unrelated")),
                                          "stop", requests))

    agent.run(_input())

    [request] = requests
    system, user = request["messages"]
    assert "이미지 분류 에이전트" in system["content"]
    # 번호 글 바로 뒤에 그 번호의 이미지
    assert user["content"] == [
        {"type": "text", "text": "이미지 3장"},
        {"type": "text", "text": "[1]"}, {"type": "image_url", "image_url": {"url": URLS[0]}},
        {"type": "text", "text": "[2]"}, {"type": "image_url", "image_url": {"url": URLS[1]}},
        {"type": "text", "text": "[3]"}, {"type": "image_url", "image_url": {"url": URLS[2]}},
    ]


def test_분류를_번호순으로_돌려준다(fake_gateway, records):
    agent = ImageTriageAgent(fake_gateway(_answer((3, "certification"), (1, "product"), (2, "package")), "stop", []))

    result = agent.run(_input())

    assert [(item.index, item.category) for item in result.items] == [
        (1, ImageCategory.PRODUCT), (2, ImageCategory.PACKAGE), (3, ImageCategory.CERTIFICATION)]


def test_모델이_빠뜨린_번호는_결과에도_없다(fake_gateway, records):
    agent = ImageTriageAgent(fake_gateway(_answer((1, "product"), (3, "specification")), "stop", []))

    assert [item.index for item in agent.run(_input()).items] == [1, 3]


def test_입력에_없는_번호를_돌려주면_실패로_알린다(fake_gateway, records):
    agent = ImageTriageAgent(fake_gateway(_answer((1, "product"), (4, "specification")), "stop", []))

    with pytest.raises(ImageTriageFailedError, match=r"\[4\]"):
        agent.run(_input())


@pytest.mark.parametrize("content", [
    _answer((1, "product"), (1, "specification")),  # 같은 번호 두 번
    _answer((1, "label")),  # 없는 분류
    "{}",
])
def test_스키마와_맞지_않는_응답은_실패로_알린다(fake_gateway, records, content):
    with pytest.raises(ImageTriageFailedError):
        ImageTriageAgent(fake_gateway(content, "stop", [])).run(_input())


def test_이미지가_없으면_모델을_부르지_않는다(fake_gateway, records):
    requests: list[dict] = []

    assert ImageTriageAgent(fake_gateway(_answer(), "stop", requests)).run(_input([])).items == []
    assert (requests, records) == ([], [])


def test_한_번에_보낼_수_있는_장수를_넘으면_부르지_않는다(fake_gateway, records):
    requests: list[dict] = []
    agent = ImageTriageAgent(fake_gateway(_answer(), "stop", requests))

    with pytest.raises(ValueError, match=str(MAX_IMAGES)):
        agent.run(_input([URLS[0]] * (MAX_IMAGES + 1)))
    assert requests == []


def test_사용량은_입력의_기록_대상_ID로_남긴다(fake_gateway, records):
    ImageTriageAgent(fake_gateway(_answer((1, "product")), "stop", [])).run(_input())

    assert (records[0]["agent"], records[0]["subject_id"]) == ("image_triage", "page-1")


def test_기본_프로필은_mini다():
    assert AGENT_PROFILES["image_triage"] == "mini"
