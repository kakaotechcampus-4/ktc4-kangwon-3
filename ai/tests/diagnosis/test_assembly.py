"""파이프라인 부품 조립을 모델·외부 호출 없이 검증한다."""

from app.diagnosis import assembly
from app.diagnosis.tracing import TracedImageSplitter
from app.schemas.schemas import ToolName


def _patch_lookups(monkeypatch) -> dict:
    """Tool 조회 경로 공장 함수를 이름표 객체로 바꾸고, 만든 객체를 기록한다."""
    made = {}

    def factory(name):
        def make():
            made[name] = object()
            return made[name]
        return make

    for name in ("case_search", "requirement_lookup", "customs_evidence_loader", "radio_item_search",
                 "food_drug_evidence_loader", "electrical_item_search", "children_item_search",
                 "advertising_evidence_loader"):
        monkeypatch.setattr(assembly, name, factory(name))
    return made


def test_Tool_6개를_이름별로_만들고_조회_경로를_한_번씩_넘긴다(monkeypatch):
    made = _patch_lookups(monkeypatch)

    tools = assembly.build_tools()

    assert set(tools) == set(ToolName)
    assert all(tool.tool_name is name for name, tool in tools.items())
    assert tools[ToolName.CUSTOMS]._case_search is made["case_search"]
    assert tools[ToolName.CUSTOMS]._requirements is made["requirement_lookup"]
    assert tools[ToolName.RADIO]._search is made["radio_item_search"]
    assert tools[ToolName.ELECTRICAL]._search is made["electrical_item_search"]
    assert tools[ToolName.CHILDREN]._search is made["children_item_search"]
    assert tools[ToolName.LABEL_AD]._evidence is made["advertising_evidence_loader"]


def test_부품은_에이전트·Tool·추출_단계를_묶고_검증은_모델이_있는_생성자로_만든다(monkeypatch):
    _patch_lookups(monkeypatch)
    built = []

    class _Agent:
        def __init__(self, *args, **kwargs):
            built.append(type(self).__name__)

    class Extraction(_Agent):
        pass

    class Selection(_Agent):
        pass

    class Verification(_Agent):
        @classmethod
        def from_env(cls):
            built.append("from_env")
            return cls()

    monkeypatch.setattr(assembly, "ExtractionAgent", Extraction)
    monkeypatch.setattr(assembly, "DecisionSelectionAgent", Selection)
    monkeypatch.setattr(assembly, "VerificationAgent", Verification)

    parts = assembly.build_parts()

    assert isinstance(parts.selector, Selection) and isinstance(parts.verifier, Verification)
    assert parts.extraction._extractor.__class__ is Extraction
    assert isinstance(parts.extraction._image_splitter, TracedImageSplitter)
    assert set(parts.tools) == set(ToolName)
    assert "from_env" in built
