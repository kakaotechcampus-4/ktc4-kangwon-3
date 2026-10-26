"""통관 근거(관세법·세관장확인 고시·대외무역법 시행령) 읽기를 실제 법제처 응답 픽스처로 확인한다."""

import pytest

from app.tools.common.law import EvidenceUnavailable
from app.tools.customs.evidence import law_key, load_customs_evidence, parse_confirmation_rows

from .conftest import AS_OF


def test_별표2를_대상_법령_행으로_나누고_삭제된_행은_뺀다(customs_evidence):
    rows = customs_evidence.rows
    numbers = [row.number for row in rows]
    assert numbers == sorted(numbers) and len(rows) == 40
    assert 4 not in numbers and 12 not in numbers  # (4)(12)는 삭제
    names = {row.law_name for row in rows}
    assert {"전파법", "어린이제품 안전 특별법", "화장품법", "의료기기법", "수입식품안전관리 특별법"} <= names


def test_법령_행은_범위와_구비요건을_함께_인용한다(customs_evidence):
    row = customs_evidence.row_for("전기용품 및 생활용품 안전관리법")  # 별표는 "안전 관리법"으로 띄어 쓴다
    assert row is not None and row.number == 9
    assert "안전인증대상 제품" in row.scope and "공급자적합성 확인신고 확인증명서" in row.requirements
    assert row.text.startswith("(9) 「전기용품") and "구비요건:" in row.text


def test_고시_제7조_단서의_생략_제외_법령과_조건을_읽는다(customs_evidence):
    exceptions = customs_evidence.omission_exceptions
    assert law_key("전기용품 및 생활용품 안전관리법") in exceptions
    assert law_key("어린이제품 안전 특별법") in exceptions
    assert law_key("전파법") not in exceptions
    assert "금지물질" in exceptions[law_key("화학물질관리법")]
    # 조건 안의 다른 고시 이름(「오ㆍ남용우려의약품 지정에 관한 규정」)을 법령으로 착각하지 않는다.
    assert law_key("오ㆍ남용우려의약품 지정에 관한 규정") not in exceptions


def test_법령_이름은_공백과_가운뎃점_차이를_무시하고_비교한다():
    assert law_key("총포·도검·화약류") == law_key("총포ㆍ도검ㆍ화약류") == law_key("총포 도검 화약류")


def test_기준일에_시행_중인_버전을_고르고_조문을_모은다(fake_law):
    evidence = load_customs_evidence(fake_law, AS_OF)
    assert ("get_law_text", "999999") not in fake_law.calls  # 시행 예정 버전은 고르지 않는다
    assert evidence.act_article.startswith("제226조(허가ㆍ승인 등의 증명 및 확인)")
    assert "상행위 이외의 목적" in evidence.decree_article
    assert evidence.notice.url.endswith("admRulSeq=2100000282502")
    assert all("OC=" not in item["url"] for item in evidence.documents())


def test_별표2가_없으면_근거로_쓰지_않는다(fake_law):
    fake_law.notice_body.annexes = [annex for annex in fake_law.notice_body.annexes if annex.annex_number != "0002"]
    with pytest.raises(EvidenceUnavailable):
        load_customs_evidence(fake_law, AS_OF)


def test_본문_식별정보가_다르면_근거로_쓰지_않는다(fake_law):
    fake_law.law_bodies["290673"] = fake_law.law_bodies["290673"].model_copy(update={"document_id": "000000"})
    with pytest.raises(EvidenceUnavailable):
        load_customs_evidence(fake_law, AS_OF)


def test_행이_없는_표는_근거로_쓰지_않는다():
    with pytest.raises(EvidenceUnavailable):
        parse_confirmation_rows("┌──┬──┐\n│대상법령 및 물품의 범위│구비요건│\n└──┴──┘")


def test_한_목에_법령이_둘이면_둘_다_생략_제외로_읽고_괄호_안_고시는_뺀다():
    from app.tools.customs.evidence import parse_omission_exceptions
    article = ("② 다음 각 호의 물품은 생략할 수 있다. 1. 사유 물품. 다만, 다음 각 목의 법령을 적용받는 물품은 세관장이 "
               "수출입요건 구비 여부를 확인한다. 가. 「가법」 및 「나법」 나. 「다법」(「라 고시」에 따른 물질에 한정한다) "
               "2. 다른 호 ③ 제3항")
    exceptions = parse_omission_exceptions(article)
    assert set(exceptions) == {law_key("가법"), law_key("나법"), law_key("다법")}
    assert "라 고시" in exceptions[law_key("다법")]


def test_단서를_읽지_못해도_나머지_근거는_쓰고_생략_목록만_비운다(fake_law):
    body = fake_law.notice_body
    fake_law.notice_body = type(body).model_validate_json(
        body.model_dump_json().replace("다만, 다음 각 목의 법령을", "다만, 다음 법령을"))
    evidence = load_customs_evidence(fake_law, AS_OF)
    assert evidence.omission_exceptions is None
    assert len(evidence.rows) == 40
