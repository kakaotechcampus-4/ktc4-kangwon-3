"""별표 원문 다듬기·나누기가 표 구조와 글자를 유지하는지 확인한다."""

from pathlib import Path

import pytest

from app.utils.annex_check import normalize, source_labels
from app.utils.annex_text import MAX_CHUNK_CHARS, MAX_CHUNK_ROWS, AnnexChunk, compact_annex, split_annex

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "annex"
_CONTENTS = sorted(_FIXTURES.glob("*/content.txt"))


def test_빈_줄과_칸을_채운_공백을_줄인다():
    content = "[별표 1]\n\n\n┃분류      │품 목　　 │세부품목     ┃   \n"

    assert compact_annex(content) == "[별표 1]\n┃분류 │품 목 │세부품목 ┃"


def test_가로선은_길이만_줄이고_교차_문자와_빈_칸은_남긴다():
    content = "┃                    ├───────────┴──────────────────────┨\n┠━━━━┼━━━━┬━━━━┨"

    assert compact_annex(content) == "┃ ├─┴─┨\n┠━┼━┬━┨"


def test_글자가_있는_줄의_선_문자는_줄이지_않는다():
    content = "┃비고: ──── 표시 ┃"

    assert compact_annex(content) == content


@pytest.mark.parametrize("path", _CONTENTS, ids=lambda path: path.parent.name)
def test_실제_별표도_테두리와_공백을_뺀_글자는_그대로다(path):
    content = path.read_text(encoding="utf-8")
    compacted = compact_annex(content)

    assert normalize(compacted) == normalize(content)
    assert len(compacted) < len(content)
    assert compacted.count("\n") <= content.count("\n")


_RADIO_1 = _FIXTURES / "방송통신기자재등의적합성평가에관한고시_별표0001-00" / "content.txt"
_SMALL = """\
[별표 1]
대상기자재
1. 가 기기
┌─┬─┐
│품목 │부호 │
┝━┿━┥
│가. 무선 │1) 기기 │A1 │
├─┼─┤
│나. 유선 │1) 기기 │B1 │
│ ├─┤
│ │2) 기기 │B2 │
├─┼─┤
│다. 기타 │1) 기기 │C1 │
└─┴─┘
2. 나 기기
┌─┬─┐
│품목 │부호 │
┝━┿━┥
│가. 무선 │1) 기기 │D1 │
└─┴─┘"""


def _joined(chunks) -> str:
    return "\n".join(chunk.content for chunk in chunks)


@pytest.mark.parametrize("path", _CONTENTS, ids=lambda path: path.parent.name)
def test_조각을_이으면_다듬은_원문과_같다(path):
    compacted = compact_annex(path.read_text(encoding="utf-8"))

    assert _joined(split_annex(compacted)) == compacted


def test_작은_별표는_조각_하나에_context가_없다():
    assert split_annex(_SMALL, max_chars=10_000) == [AnnexChunk(content=_SMALL)]


def test_큰_표는_합친_칸이_모두_끝나는_가로선에서_나누고_머리글을_context로_붙인다():
    chunks = split_annex(_SMALL, max_chars=90)

    assert [chunk.content.splitlines()[0] for chunk in chunks] == ["[별표 1]", "├─┼─┤", "├─┼─┤", "2. 나 기기"]
    # 부분 가로선(│ ├─┤)에서는 나누지 않아 나.의 두 행이 같은 조각에 있음
    assert chunks[1].content == "├─┼─┤\n│나. 유선 │1) 기기 │B1 │\n│ ├─┤\n│ │2) 기기 │B2 │"
    assert chunks[0].context == ""
    # 별표 제목은 한 번만
    assert chunks[1].context == chunks[2].context == "[별표 1]\n대상기자재\n1. 가 기기\n┌─┬─┐\n│품목 │부호 │\n┝━┿━┥"
    assert chunks[3].context == "[별표 1]\n대상기자재"
    assert _joined(chunks) == _SMALL


def test_행_수_한도를_넘으면_글자가_적어도_나눈다():
    chunks = split_annex(_SMALL, max_chars=10_000, max_rows=2)

    assert [sum(source_labels(chunk.content).values()) for chunk in chunks] == [1, 2, 1, 1]
    assert _joined(chunks) == _SMALL


@pytest.mark.parametrize("path", _CONTENTS, ids=lambda path: path.parent.name)
def test_한도를_넘는_조각은_더_나눌_가로선이_없는_묶음뿐이다(path):
    for chunk in split_annex(compact_annex(path.read_text(encoding="utf-8"))):
        lines = chunk.content.splitlines()
        if len(chunk.content) > MAX_CHUNK_CHARS or sum(source_labels(chunk.content).values()) > MAX_CHUNK_ROWS:
            assert not any(line[0] in "├┝┠" for line in lines[1:])


def test_전파_고시_별표1은_조각으로_나뉘고_뒤_조각은_별표_제목을_받는다():
    chunks = split_annex(compact_annex(_RADIO_1.read_text(encoding="utf-8")))

    assert len(chunks) > 1
    assert all(chunk.context.startswith("[별표 1]\n적합성평가 대상기자재") for chunk in chunks[1:])
    # 표 중간에서 시작하는 조각은 대분류 제목과 머리글(굵은 가로선까지)을 context로 받음
    middle = [chunk for chunk in chunks if chunk.content.startswith("├")]
    assert middle
    assert all("11. 전자파장해를 주거나 전자파로부터 영향을 받는 기기" in chunk.context for chunk in middle)
    assert all(chunk.context.splitlines()[-1].startswith("┝") for chunk in middle)
