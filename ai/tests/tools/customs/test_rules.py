import pytest

from app.tools.customs.rules import sale_actions


def test_할_일은_법령당_한_건이고_머리말_할_일_서류_구매대행을_줄로_나눈다():
    # #640: 법령마다 200자짜리 사입·구매대행 2문장이 나오던 것을 한 건으로.
    # 11/9 실사이트 화면에서 한 문장도 읽기 어려워 줄로 나누고 쉬운 말로 풀었다
    [action] = sale_actions("전파법", ["8543709090", "9019102000"], None, ["방송통신기기인증확인서"],
                            ["국립전파연구원"], ("omittable", ""))
    assert action.split("\n") == [
        "[전파법] · 품목번호 HS 8543.70-9090, 9019.10-2000 후보",
        "수입 통관 때 세관에 아래 서류를 내야 할 수 있습니다.",
        "- 미리 갖출 서류: 방송통신기기인증확인서 (관세법 제226조, 세관장확인 고시 별표 2)",
        "- 구매대행: 구매자 개인이 쓰려고 들여오는 경우 등에는 생략될 수 있음",
    ]
    # 확인 기관 나열과 판매자가 모르는 용어는 쓰지 않음
    assert "국립전파연구원" not in action and "세관장확인을" not in action and "제19조" not in action


def test_생략_제외_법령은_구매대행도_해당한다고_적는다():
    [action] = sale_actions("전기용품 및 생활용품 안전관리법", ["8543709090"], None, ["전기용품 및 생활용품 요건확인서"],
                            [], ("excepted", ""))
    assert action.split("\n")[-1] == "- 구매대행도 해당"
    assert "- 미리 갖출 서류: 전기용품 및 생활용품 요건확인서 (관세법 제226조, 세관장확인 고시 별표 2)" in action


def test_고시가_생략_제외_범위를_좁힌_법령은_그_조건을_함께_적는다():
    # 조건을 빼면 '구매대행도 해당'이 고시보다 넓은 안내가 된다 (약사법은 오·남용우려 의약품에 한정 등)
    condition = "(「수입식품안전관리특별법 시행규칙」 별표 8의2 제2호에 해당하는 식품등은 제외한다)"
    [action] = sale_actions("수입식품안전관리 특별법", ["3924100000"], None, [], [], ("excepted", condition))
    assert action.split("\n")[-1] == ("- 구매대행도 해당 (고시 조건: 「수입식품안전관리특별법 시행규칙」 별표 8의2 제2호에 "
                                      "해당하는 식품등은 제외한다)")
    assert "- 미리 갖출 서류: 해당 법령의 요건 확인 서류 (관세법 제226조, 세관장확인 고시 별표 2)" in action


def test_고시를_못_읽었으면_구매대행_생략_여부를_확인하지_못했다고_적는다():
    [action] = sale_actions("전파법", ["8516799000"], None, ["방송통신기기인증확인서"], [], None)
    assert action.split("\n")[-1] == "- 구매대행: 생략 여부를 확인하지 못함"


@pytest.mark.parametrize("law,note", [
    ("약사법", "의약품·의약외품·한약재·동물용 의약품에만 해당합니다."),
    ("의료기기법", "의료기기(동물용 포함)에만 해당합니다."),
    ("생활화학제품 및 살생물제의 안전관리에 관한 법률", "세정제·세탁세제·방향제·탈취제·접착제 같은 안전확인대상 생활화학제품에만 해당합니다."),
    ("화장품법", "화장품(피부·모발에 바르거나 뿌리는 등으로 쓰는 물품)에만 해당합니다."),
    # GW는 "위생용품관리법", 고시는 "위생용품 관리법"으로 띄어 씀
    ("위생용품관리법", "세척제(채소·과일·식기용), 칫솔·치실, 일회용 컵·수저·빨대, 화장지·물티슈, 일회용 기저귀·면봉 등 "
                   "「위생용품 관리법」에서 위생용품으로 정한 물품에만 해당합니다."),
])
def test_HS에_묶여_오지만_일부_물품에만_해당하는_법령에_대상_물품_조건을_덧붙인다(law, note):
    # #809: 디퓨저·젖병에 약사법, 크림에 위생용품관리법이 조건 없이 "필요할 수 있음"으로 나가던 것
    from app.tools.customs.rules import law_note
    assert law_note(law) == note


def test_야생생물법에는_멸종위기종_제품에만_해당한다는_설명을_덧붙인다():
    from app.tools.customs.rules import law_note

    [action] = sale_actions("야생생물 보호 및 관리에 관한 법률(허가)", ["4202311090"], None,
                            ["국제적멸종위기 동식물 수입허가서"], [], ("excepted", ""))
    lines = action.split("\n")
    assert lines[1] == ("이 품목번호로 분류되고 악어·뱀 등 멸종위기종(CITES) 가죽이나 부위를 쓴 제품에 해당하면, "
                        "통관 시 아래 서류가 필요할 수 있습니다.")
    assert lines[-2:] == ["- 구매대행도 해당", "- 소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다."]
    assert law_note("야생생물 보호 및 관리에 관한 법률") == law_note("야생생물 보호 및 관리에 관한 법률(허가)")
    assert law_note("전파법") is None


def test_일부_물품에만_해당하는_법령의_할_일은_대상_물품을_먼저_적고_끝에_참고로_붙이지_않는다():
    # #820 리뷰: 조건을 끝 "참고"에만 붙이면 판매자·검증 모델이 이 상품에 서류가 필요하다는 안내로 먼저 읽음
    [action] = sale_actions("약사법", ["3924909000"], None, ["표준통관예정보고서"], [], ("omittable", ""))
    assert action.split("\n") == [
        "[약사법] · 품목번호 HS 3924.90-9000 후보",
        "이 품목번호로 분류되고 의약품·의약외품·한약재·동물용 의약품에 해당하면, 통관 시 아래 서류가 필요할 수 있습니다.",
        "- 미리 갖출 서류: 표준통관예정보고서 (관세법 제226조, 세관장확인 고시 별표 2)",
        "- 구매대행: 구매자 개인이 쓰려고 들여오는 경우 등에는 생략될 수 있음",
    ]
    assert "참고:" not in action


def test_GW가_법령_이름에_요건_종류를_붙여도_같은_법령으로_본다():
    from app.tools.customs.evidence import law_key
    from app.tools.customs.rules import omission_status

    assert law_key("야생생물 보호 및 관리에 관한 법률(허가)") == law_key("야생생물 보호 및 관리에 관한 법률")
    exceptions = {law_key("야생생물 보호 및 관리에 관한 법률"): ""}
    assert omission_status("야생생물 보호 및 관리에 관한 법률(허가)", exceptions) == ("excepted", "")


def test_상품_신호가_False일_때만_조건부_요건을_뺀다():
    from app.schemas.product import Product
    from app.tools.customs.rules import excluded_by_product

    law = "총포･도검･화약류 등의 안전관리에 관한 법률"
    assert excluded_by_product(law, Product(product_id="p", weapon_like=False)) is not None
    assert excluded_by_product(law, Product(product_id="p", weapon_like=True)) is None
    assert excluded_by_product(law, Product(product_id="p")) is None
    # 조건이 없는 법령은 신호와 상관없이 남김
    assert excluded_by_product("어린이제품 안전 특별법", Product(product_id="p", weapon_like=False)) is None


def test_야생생물법은_가축_가죽이_명시되고_멸종위기종_표기가_없을_때만_뺀다():
    from app.schemas.product import Product
    from app.tools.customs.rules import excluded_by_product

    law = "야생생물 보호 및 관리에 관한 법률(허가)"
    product = Product(product_id="p")
    assert excluded_by_product(law, product, ["탑 레이어 소가죽"]) is not None
    assert excluded_by_product(law, product, ["소가죽 RFID 차단 지갑"]) is not None
    assert excluded_by_product(law, product, ["Genuine Cowhide Leather"]) is not None
    assert excluded_by_product(law, product, ["인조가죽(PU)"]) is not None
    # 멸종위기종 표기가 같이 있으면 남김 (악어 무늬처럼 무늬만 말해도 안전한 쪽으로)
    assert excluded_by_product(law, product, ["소가죽, 악어 무늬 프린트"]) is None
    assert excluded_by_product(law, product, ["파이톤 가죽"]) is None
    # 소재를 모르거나 가죽 종류가 없으면 남김
    assert excluded_by_product(law, product, ["가죽"]) is None
    # 송아지 가죽은 가죽을 붙인 표기만 본다. '스카프', 'mid-calf'(종아리)는 소재 표기가 아니다 (리뷰 #708)
    assert excluded_by_product(law, product, ["캐시미어 스카프"]) is None
    assert excluded_by_product(law, product, ["울 스카프 (소재: 울 100%)"]) is None
    assert excluded_by_product(law, product, ["Mid-calf leather boots"]) is None
    assert excluded_by_product(law, product, ["카프스킨 반지갑"]) is not None
    assert excluded_by_product(law, product, ["카프 가죽 벨트"]) is not None
    assert excluded_by_product(law, product, ["Genuine calfskin wallet"]) is not None
    assert excluded_by_product(law, product, ["Genuine calf hide belt"]) is not None
    # 'calf leather'는 종아리 뜻으로도 쓰여 빼는 표기로 보지 않는다 (남기는 쪽)
    assert excluded_by_product(law, product, ["Wide calf leather boots"]) is None
    # 일부 소재만 확인된 상품은 남긴다. 안감은 인조 소재인데 겉감 가죽의 종류는 모르는 경우 (리뷰 #708)
    assert excluded_by_product(law, product, ["겉감: 가죽, 안감: PVC"]) is None
    assert excluded_by_product(law, product, ["천연가죽 가방 (안감 PVC 가죽)"]) is None
    assert excluded_by_product(law, product, ["겉감 천연가죽, 안감 인조가죽"]) is None
    assert excluded_by_product(law, product, ["Genuine leather, PU leather lining"]) is None
    assert excluded_by_product(law, product, ["겉감 가죽, 안감 돈피(피그스킨)"]) is None
    # 'PVC'만으로는 인조 가죽 표기로 보지 않는다 ('PVC 무첨가'는 PVC가 없다는 말)
    assert excluded_by_product(law, product, ["PVC 무첨가 친환경 소재"]) is None
    assert excluded_by_product(law, product, ["PVC 가죽 가방"]) is not None
    # 뺄 수 있는 표기 바로 뒤의 가죽 낱말은 같은 소재라 남은 가죽으로 세지 않는다
    assert excluded_by_product(law, product, ["Genuine Cowhide Leather wallet"]) is not None
    assert excluded_by_product(law, product, ["소가죽 레더 카드지갑"]) is not None
    # 모피(fur)는 낱말일 때만 남긴다. 'Furla', 'furniture' 안의 글자는 모피 표기가 아니다
    assert excluded_by_product(law, product, ["Furla 소가죽 지갑"]) is not None
    assert excluded_by_product(law, product, ["소가죽 가구 furniture"]) is not None
    assert excluded_by_product(law, product, ["소가죽 장갑, 밍크 fur 안감"]) is None
    assert excluded_by_product(law, product, ["cowhide gloves with rabbit furs"]) is None
    assert excluded_by_product(law, product, ["소가죽 장갑 fur안감"]) is None
    assert excluded_by_product(law, product, []) is None
    assert excluded_by_product(law, product) is None


def test_서류는_고시_별표_2_구비요건을_따르고_대상마다_짝지어_조건을_살린다():
    # luna 전환 측정: GW 서류명("수입승인서")이 인용한 고시 구비요건("위생용품의 수입신고 확인증")과 달라 검증이 막음
    from app.tools.customs.evidence import ConfirmationRow
    from app.tools.customs.rules import documents_text, notice_documents
    hygiene = ConfirmationRow(38, "위생용품 관리법", "(38) 「위생용품 관리법」해당 물품",
                              "ㅇ지방식품의약품안전청장의 위생용품의 수입신고 확인증")
    electrical = ConfirmationRow(9, "전기용품 및 생활용품 안전 관리법",
                                 "(9) 「전기용품 및 생활용품 안전 관리법」해당 물품 (가)안전인증대상 제품 (나)안전확인대상 제품 "
                                 "(다)공급자 적합성 확인대상 제품",
                                 "ㅇ세관장 확인물품 확인증 ㅇ세관장 확인물품 확인증 ㅇ공급자적합성 확인신고 확인증명서(단,전기용품에 한함)")
    children = ConfirmationRow(36, "어린이제품 안전 특별법", "(36) 「어린이제품 안전 특별법」해당 물품",
                               "ㅇ어린이제품 동일모델 확인증 ㅇ사전통관대상 어린이제품 확인증")
    assert notice_documents(hygiene) == ["지방식품의약품안전청장의 위생용품의 수입신고 확인증"]
    assert notice_documents(electrical) == ["안전인증대상 제품: 세관장 확인물품 확인증", "안전확인대상 제품: 세관장 확인물품 확인증",
                                            "공급자 적합성 확인대상 제품: 공급자적합성 확인신고 확인증명서(단,전기용품에 한함)"]
    # 대상 하위 항목이 없으면 구비요건 항목을 그대로 나열
    assert documents_text(notice_documents(children)) == (
        "물품에 따라 아래 중 해당하는 서류: 어린이제품 동일모델 확인증 / 사전통관대상 어린이제품 확인증")
    assert notice_documents(None) == []


def test_고시_구비요건을_읽지_못하면_GW_서류명을_쓴다():
    [action] = sale_actions("위생용품관리법", ["3924100000"], None, ["수입승인서"], [], None)
    assert "- 미리 갖출 서류: 수입승인서 (관세법 제226조, 세관장확인 고시 별표 2)" in action
