from app.tools.customs.rules import sale_actions


def test_할_일은_법령당_한_문장이고_서류와_구매대행_생략_여부를_담는다():
    # #640: 법령마다 200자짜리 사입·구매대행 2문장이 나와 할 일이 길어지던 것을 한 문장으로
    [action] = sale_actions("수입식품안전관리 특별법", ["3924100000"], None, ["수입식품등 수입신고확인증"],
                            ["식품의약품안전처"], ("omittable", ""))
    assert action.startswith("[「수입식품안전관리 특별법」 · HS 3924.10-0000 후보] 이 HS로 분류되면 수입신고 때 세관장확인을 받아야 하고")
    assert "구매대행 수입은 세관장확인을 생략할 수 있습니다" in action
    assert "미리 갖출 서류: 수입식품등 수입신고확인증(관세법 제226조, 세관장확인 고시 별표 2)." in action
    # 확인 기관 8곳 나열은 문장에서 뺌
    assert "식품의약품안전처" not in action


def test_생략_제외_법령은_구매대행도_생략할_수_없다고_적는다():
    condition = "(「수입식품안전관리특별법 시행규칙」 별표 8의2 제2호에 해당하는 식품등은 제외한다)"
    [action] = sale_actions("수입식품안전관리 특별법", ["3924100000"], None, [], [], ("excepted", condition))
    assert "구매대행 수입도 세관장확인을 생략할 수 없습니다(세관장확인 고시 제7조 제2항 제1호 단서)" in action
    assert "미리 갖출 서류: 해당 법령의 요건 확인 서류" in action


def test_고시를_못_읽었으면_구매대행_생략_여부를_확인_필요로_적는다():
    [action] = sale_actions("전파법", ["8516799000"], None, ["방송통신기기인증확인서"], [], None)
    assert "구매대행 수입의 세관장확인 생략 여부는 확인이 필요합니다" in action


def test_야생생물법에는_멸종위기종_제품에만_해당한다는_설명을_덧붙인다():
    from app.tools.customs.rules import law_note

    [action] = sale_actions("야생생물 보호 및 관리에 관한 법률(허가)", ["4202311090"], None,
                            ["국제적멸종위기 동식물 수입허가서"], [], ("excepted", ""))
    assert action.endswith("소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다.")
    assert law_note("야생생물 보호 및 관리에 관한 법률") == law_note("야생생물 보호 및 관리에 관한 법률(허가)")
    assert law_note("전파법") is None


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
    assert excluded_by_product(law, product, []) is None
    assert excluded_by_product(law, product) is None
