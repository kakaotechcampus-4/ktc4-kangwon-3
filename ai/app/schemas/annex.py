"""법령·행정규칙 별표 파싱 결과와 저장 레코드.

대상품목 별표(예: 안전인증대상전기용품 세부품목)를 품목 행 단위로 풀어 임베딩 조각으로 쓰기 위한 구조.
파서는 별표 원본 파일(HWP·HWPX)의 표를 읽어 AnnexParseOutput을 만들고, 출처·검증 결과는 레코드에 함께 담음.
비고 계열(conditions·exclusions·inclusions·notes)은 원문 문구 그대로 담음.
저전압 포함 여부 등 판단 값은 담지 않고 적재 코드가 이 문구에서 계산함.
"""

from .base import StrictModel


# -- 파싱 결과 --

class AnnexAttribute(StrictModel):
    """표마다 다른 칸 하나 (예: 기기부호, 적용 안전기준, 확인서류).

    나열된 값은 항목마다 나눠 담음. 대표 품목을 품목 단위로 검색·대조하기 위함.

    Attributes:
        name: 원문 열 이름 (예: "대표 품목", "기기부호").
        values: 칸 값. 나열이면 항목마다 하나, 아니면 하나 (예: ["노트북(랩탑)", "태블릿"], ["LARN8"]).
    """

    name: str
    values: list[str]


class AnnexItem(StrictModel):
    """품목 행 하나. 임베딩 조각 하나가 됨.

    Attributes:
        category_path: 분류 계층, 상위부터 (예: ["7. 전기기기", "아. 전기액체 가열기기"]).
        item_label: 원문 번호 (예: "③"). 없으면 None.
        item_name: 품목명 (예: "전기주전자").
        conditions: 한정 문구. 묶음 비고는 묶음의 모든 품목에 붙임
            (예: "교류전압을 사용하는 제품에 한정하며").
        exclusions: 제외 문구 (예: "통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다").
        inclusions: 포함 문구 (예: "교류전원 30V 이하, 직류 전원 42V 이하에서 사용하는 것을 포함한다").
        attributes: 표마다 다른 칸 목록.
        source_text: 원문에서 이 행에 해당하는 글자. 원문 대조 검증용.
    """

    category_path: list[str]
    item_label: str | None
    item_name: str
    conditions: list[str]
    exclusions: list[str]
    inclusions: list[str]
    attributes: list[AnnexAttribute]
    source_text: str


class AnnexSkippedRow(StrictModel):
    """일부러 뺀 행. 누락과 구분하기 위해 남김.

    Attributes:
        category_path: 뺀 행이 속한 분류 계층, 상위부터. 어느 분류가 "대상 없음"인지 남기기 위함
            (예: ["1. 안전인증대상전기용품", "다. 전원용 커패시터 및 전원필터"]).
        item_label: 원문 번호. 없으면 None.
        reason: 뺀 이유 (예: "삭제 <2023. 3. 20.>", "대상 없음").
    """

    category_path: list[str]
    item_label: str | None
    reason: str


class AnnexParseOutput(StrictModel):
    """별표 하나의 파싱 결과.

    Attributes:
        scheme: 규제 구분 (예: "안전인증대상전기용품", "적합성평가 대상기자재").
        items: 품목 행 목록.
        skipped: 일부러 뺀 행 목록.
        notes: 표 전체에 걸리는 공통 비고 문구
            (예: "1차 전지(건전지) 및 2차 전지(충전지)만을 전원으로 사용하는 구조의 것은 … 제외한다.").
    """

    scheme: str
    items: list[AnnexItem]
    skipped: list[AnnexSkippedRow]
    notes: list[str]


# -- 저장 레코드 --

class AnnexSource(StrictModel):
    """별표 출처. 클라이언트 응답에서 코드가 채움. 임베딩하지 않고 필터·버전 관리에 씀.

    Attributes:
        document_name: 법령명 또는 행정규칙명.
        document_kind: "law" 또는 "admrul".
        version_key: 버전 키 (법령 mst, 행정규칙 serial_number).
        law_type: 법종구분 또는 행정규칙종류 (법률, 대통령령, ○○부령, 고시 등).
        enforce_date: 시행일자 (YYYYMMDD).
        annex_number: 별표번호 (예: "0001").
        annex_branch_number: 별표가지번호 (예: "00").
        annex_title: 별표제목.
        file_url: 별표 원본 파일 링크.
    """

    document_name: str
    document_kind: str
    version_key: str
    law_type: str | None
    enforce_date: str | None
    annex_number: str
    annex_branch_number: str | None
    annex_title: str
    file_url: str | None


class AnnexParseRecord(StrictModel):
    """적재에 저장하는 별표 파싱 결과. 파싱 결과 + 출처 + 검증 결과.

    Attributes:
        source: 별표 출처.
        output: 파싱 결과. 검증에 실패해도 남김(어느 행이 틀렸는지 확인용).
            적재는 verified일 때만 쓰고, 아니면 원문 조각으로 대체. 파싱하지 못했으면 None.
        verified: 검증 통과 여부.
        failure_reasons: 검증 실패 이유 (원문에 없는 문구, 누락된 번호 등).
    """

    source: AnnexSource
    output: AnnexParseOutput | None
    verified: bool
    failure_reasons: list[str]
