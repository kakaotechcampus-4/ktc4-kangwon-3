"""별표 규칙 파서 평가 러너의 대상 고르기·덤프 이름 규칙을 확인한다."""

from app.eval.annex_file_runner import TARGETS, dump_name, select_annex
from app.eval.annex_scoring import ANNEX_TRUTH_DIR
from app.schemas.clients.law_response import LawAnnex


def test_덤프_이름은_정답_파일_이름과_같은_규칙이다():
    assert dump_name("전기용품 및 생활용품 안전관리 운용요령", "0004", "00") == "전기용품및생활용품안전관리운용요령_별표0004-00"
    targets = {dump_name(document.name, number, branch) for document in TARGETS for number, branch in document.annexes}
    assert {path.stem for path in ANNEX_TRUTH_DIR.glob("*.json")} <= targets


def test_같은_번호의_서식은_빼고_가지번호까지_맞는_별표를_고른다():
    annexes = [
        LawAnnex(annex_number="0007", annex_branch_number="00", annex_type="별표", annex_title="어린이보호포장대상제품"),
        LawAnnex(annex_number="0007", annex_branch_number="02", annex_type="서식", annex_title="신청서"),
        LawAnnex(annex_number="0007", annex_branch_number="02", annex_type="별표", annex_title="안전성검사대상전기용품"),
    ]

    assert select_annex(annexes, "0007", "02").annex_title == "안전성검사대상전기용품"
    assert select_annex(annexes, "0008", "00") is None


def test_대상_별표는_22개다():
    assert sum(len(document.annexes) for document in TARGETS) == 22
