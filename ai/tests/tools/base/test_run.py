"""ToolRun: 실행마다 새 상태를 갖고, 기본 query 카운터를 채움."""

from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import ToolName
from app.tools.base import ToolRun


def _run() -> ToolRun:
    return ToolRun(Product(product_id="p-1"), ToolSelectionItem(tool_name=ToolName.RADIO, selected=True, reason="무선"))


def test_query는_5개_Tool_공통_카운터로_시작한다():
    assert _run().query == {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0}


def test_실행마다_목록과_query를_따로_갖는다():
    first, second = _run(), _run()
    first.assumptions.append("가정")
    first.missing.append("product_type")
    first.query["dropped_facts"] = 2

    assert second.assumptions == []
    assert second.missing == []
    assert second.query["dropped_facts"] == 0


def test_추출_전에는_조건이_비어_있다():
    run = _run()

    assert run.extracted is None
    assert (run.snippets, run.facts, run.by_field) == ({}, [], {})
