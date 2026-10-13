"""대상 별표 원본 파일을 법제처에서 받아 규칙 파서로 풀고, 원문 대조·정답 채점·덤프를 남긴다.

    python -m app.eval.annex_file_runner                     # 대상 별표 전부
    python -m app.eval.annex_file_runner --only 운용요령      # 덤프 이름에 들어간 글자로 고르기

법령·행정규칙 검색 → 현행 본문 조회 → 별표 파일 받기 → 표 모양별 규칙 → API 별표내용과 원문 대조
→ 원본 파일과 거꾸로 대조하는 점검 (빠진 줄·번호 줄, 안 붙은 비고).
정답셋(tests/eval_truth_annex/)이 있는 별표는 채점까지 함. LLM을 부르지 않아 비용이 없음 (법제처 호출만).
덤프는 data/annex_file_parser/<문서명>_별표<번호>-<가지>/ (커밋 안 함)
    original.<hwp|hwpx>: 받은 원본 파일 / content.txt: API 별표내용
    parsed.json: AnnexParseRecord / meta.json: 출처·파일·고른 규칙·파싱 시간·점검 결과
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..clients.law import AdmrulSearchClient, AdmrulTextClient, AnnexFileClient, LawSearchClient, LawTextClient
from ..config import load_settings
from ..schemas.annex import AnnexParseRecord, AnnexSource
from ..schemas.clients.law_request import AnnexFileRequest, LawSearchRequest, LawTextRequest
from ..schemas.clients.law_response import LawAnnex
from ..utils.annex_check import check_annex
from ..utils.annex_file import parse_annex, read_annex_file
from .annex_file_audit import audit_annex
from .annex_scoring import ANNEX_TRUTH_DIR, AnnexScore, load_annex_truth, score_annex

_AI_ROOT = Path(__file__).resolve().parents[2]
DUMP_DIR = _AI_ROOT / "data" / "annex_file_parser"


@dataclass(frozen=True)
class AnnexDocument:
    """대상 별표가 있는 문서.

    Attributes:
        kind: "law"(법령) 또는 "admrul"(행정규칙).
        name: 법령명·행정규칙명 (검색 결과와 정확히 같아야 함).
        annexes: 대상 별표 (별표번호 4자리, 가지번호 2자리).
    """

    kind: str
    name: str
    annexes: tuple[tuple[str, str], ...]


# 6개 소관 분야 대상품목 별표 (의료기기 품목 및 등급은 표가 아닌 줄 목록이라 제외)
TARGETS = (
    AnnexDocument("law", "전기용품 및 생활용품 안전관리법 시행규칙",
                  (("0003", "00"), ("0004", "00"), ("0005", "00"), ("0006", "00"), ("0007", "00"), ("0007", "02"),
                   ("0013", "00"))),
    AnnexDocument("admrul", "전기용품 및 생활용품 안전관리 운용요령",
                  (("0001", "00"), ("0002", "00"), ("0003", "00"), ("0003", "02"), ("0004", "00"), ("0005", "00"),
                   ("0006", "00"), ("0007", "00"))),
    AnnexDocument("law", "어린이제품 안전 특별법 시행규칙", (("0001", "00"), ("0002", "00"), ("0003", "00"))),
    AnnexDocument("law", "전파법 시행령", (("0006", "02"),)),
    AnnexDocument("admrul", "방송통신기자재등의 적합성평가에 관한 고시", (("0001", "00"),)),
    AnnexDocument("admrul", "관세법 제226조에 따른 세관장확인물품 및 확인방법 지정고시", (("0001", "00"), ("0002", "00"))),
)


def dump_name(document_name: str, number: str, branch: str) -> str:
    """덤프 폴더·정답 파일 이름 (예: "전기용품및생활용품안전관리운용요령_별표0004-00")."""
    return f"{''.join(document_name.split())}_별표{number}-{branch}"


def select_annex(annexes: list[LawAnnex], number: str, branch: str) -> LawAnnex | None:
    """본문 별표 목록에서 번호·가지번호가 같은 별표를 고른다. 같은 번호의 서식은 뺌."""
    return next((annex for annex in annexes
                 if annex.annex_number == number and (annex.annex_branch_number or "00") == branch
                 and annex.annex_type in (None, "별표")), None)


def fetch_document(document: AnnexDocument, oc: str) -> tuple[list[LawAnnex], dict]:
    """현행 본문을 받아 (별표 목록, 출처 공통 필드)를 돌려준다.

    Raises:
        LookupError: 이름이 같은 현행 문서가 검색되지 않은 경우.
    """
    request = LawSearchRequest(query=document.name)
    if document.kind == "law":
        found = LawSearchClient(oc=oc).fetch_parsed(request).items
        current = next((item for item in found if item.law_name == document.name and item.history_status == "현행"),
                       None)
        if current is None:
            raise LookupError(f"현행 법령을 찾지 못함: {document.name}")
        text = LawTextClient(oc=oc).fetch_parsed(LawTextRequest(mst=current.mst))
        common = {"version_key": text.mst, "law_type": text.law_type, "enforce_date": text.enforce_date}
    else:
        found = AdmrulSearchClient(oc=oc).fetch_parsed(request).items
        current = next((item for item in found if item.name == document.name and item.history_status == "현행"),
                       None)
        if current is None:
            raise LookupError(f"현행 행정규칙을 찾지 못함: {document.name}")
        text = AdmrulTextClient(oc=oc).fetch_parsed(LawTextRequest(mst=current.serial_number))
        common = {"version_key": text.serial_number, "law_type": text.rule_type, "enforce_date": text.enforce_date}
    return text.annexes, {"document_name": document.name, "document_kind": document.kind, **common}


def run_annex(annex: LawAnnex, common: dict, files: AnnexFileClient, out_dir: Path) -> dict:
    """별표 하나를 받아 풀고 덤프를 남긴다. 실패해도 기록을 남기고 넘어감."""
    source = AnnexSource(**common, annex_number=annex.annex_number, annex_branch_number=annex.annex_branch_number,
                         annex_title=annex.annex_title or "", file_url=annex.file_url)
    name = dump_name(source.document_name, source.annex_number, source.annex_branch_number or "00")
    directory = out_dir / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "content.txt").write_text(annex.annex_content or "", encoding="utf-8")
    result = {"name": name, "rule": None, "error": None, "parse_ms": None, "file_name": None, "audit": {}}
    output = None
    reasons: list[str] = []
    try:
        if not annex.file_url:
            raise ValueError("별표 파일 링크가 없습니다.")
        file = files.fetch_parsed(AnnexFileRequest(file_url=annex.file_url))
        result["file_name"] = file.file_name
        (directory / f"original.{file.file_type}").write_bytes(file.content)
        started = perf_counter()
        blocks = read_annex_file(file.content, file.file_type)
        result["rule"], output = parse_annex(blocks)
        result["parse_ms"] = round((perf_counter() - started) * 1000, 1)
        reasons = check_annex(annex.annex_content or "", output)
        result["audit"] = {kind: found for kind, found in audit_annex(blocks, output).items() if found}
    except (ValueError, RuntimeError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    record = AnnexParseRecord(source=source, output=output, verified=output is not None and not reasons,
                              failure_reasons=reasons if output is not None else [result["error"]])
    (directory / "parsed.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    (directory / "meta.json").write_text(
        json.dumps({"source": source.model_dump(), **result}, ensure_ascii=False, indent=2), encoding="utf-8")
    result.update(verified=record.verified, failure_reasons=record.failure_reasons,
                  items=len(output.items) if output else 0, skipped=len(output.skipped) if output else 0,
                  notes=len(output.notes) if output else 0, score=_score(name, record))
    return result


def _score(name: str, record: AnnexParseRecord) -> dict | None:
    truth_path = ANNEX_TRUTH_DIR / f"{name}.json"
    if record.output is None or not truth_path.exists():
        return None
    _, truth = load_annex_truth(truth_path)
    score: AnnexScore = score_annex(truth, record.output)
    return asdict(score)


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=_AI_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def report(results: list[dict], seconds: float) -> None:
    """별표별 한 줄 요약과 실패 사유·채점 결과를 출력한다."""
    for result in results:
        status = "오류" if result["error"] else ("통과" if result["verified"] else "대조 실패")
        print(f"{status:5} {result['rule'] or '-':11} 행 {result['items']:3} · 뺀 행 {result['skipped']:2} · "
              f"비고 {result['notes']:2} · 파싱 {result['parse_ms'] or 0:6.1f}ms  {result['name']}")
        for reason in result["failure_reasons"][:5]:
            print(f"      - {reason}")
        for kind, found in result["audit"].items():
            print(f"      ! {kind} {len(found)}건: {found[0]}")
        if score := result["score"]:
            print(f"      정답 {score['matched_rows']}/{score['expected_rows']} · 누락 {len(score['missing'])} · "
                  f"초과 {len(score['extra'])} · 분류 오류 {len(score['category_errors'])} · "
                  f"칸 오류 {len(score['field_errors'])} · 규제 구분 {score['scheme_ok']} · "
                  f"뺀 행 {score['skipped_ok']} · 비고 {score['notes_ok']}")
    verified = sum(result["verified"] for result in results)
    audited = sum(not result["audit"] for result in results)
    parse_ms = sum(result["parse_ms"] or 0 for result in results)
    print(f"\n대조 통과 {verified}/{len(results)} · 점검 이상 없음 {audited}/{len(results)} · "
          f"파싱 합계 {parse_ms:.0f}ms · 전체(받기 포함) {seconds:.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="덤프 이름에 이 글자가 들어간 별표만")
    parser.add_argument("--out", type=Path, default=DUMP_DIR, help="덤프 폴더")
    args = parser.parse_args()

    oc = load_settings().law_oc
    files = AnnexFileClient()
    started = perf_counter()
    results: list[dict] = []
    for document in TARGETS:
        wanted = [(number, branch) for number, branch in document.annexes
                  if not args.only or args.only in dump_name(document.name, number, branch)]
        if not wanted:
            continue
        annexes, common = fetch_document(document, oc)
        for number, branch in wanted:
            annex = select_annex(annexes, number, branch)
            if annex is None:
                print(f"! 본문에 별표가 없음: {dump_name(document.name, number, branch)}", file=sys.stderr)
                continue
            results.append(run_annex(annex, common, files, args.out))
    seconds = perf_counter() - started

    dirty = _git("status", "--porcelain", "--", ".")
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "git_dirty": None if dirty is None else bool(dirty),
        "seconds": round(seconds, 1),
        "results": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report(results, seconds)
    return 0 if results and all(result["verified"] and not result["audit"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
