from app.tools.customs.rules import sale_actions


def test_제출_서류_뒤_조사는_받침에_맞춘다():
    with_final = sale_actions("수입식품안전관리 특별법", ["3924100000"], None, ["수입식품등 수입신고확인증"],
                              ["식품의약품안전처"], ("omittable", ""))[0]
    without_final = sale_actions("전파법", ["8516799000"], None, ["방송통신기기인증확인서"],
                                 ["국립전파연구원"], ("omittable", ""))[0]
    assert "수입신고확인증을 미리" in with_final
    assert "인증확인서를 미리" in without_final


def test_단서_조건의_바깥_괄호는_한_겹만_남긴다():
    condition = "(「수입식품안전관리특별법 시행규칙」 별표 8의2 제2호에 해당하는 식품등은 제외한다)"
    agent = sale_actions("수입식품안전관리 특별법", ["3924100000"], None, [], [], ("excepted", condition))[1]
    assert "단서 조건: 「수입식품안전관리특별법 시행규칙」 별표 8의2 제2호에 해당하는 식품등은 제외한다)." in agent
    assert "))" not in agent


def test_GW가_법령_이름에_요건_종류를_붙여도_같은_법령으로_본다():
    from app.tools.customs.evidence import law_key
    from app.tools.customs.rules import omission_status

    assert law_key("야생생물 보호 및 관리에 관한 법률(허가)") == law_key("야생생물 보호 및 관리에 관한 법률")
    exceptions = {law_key("야생생물 보호 및 관리에 관한 법률"): ""}
    assert omission_status("야생생물 보호 및 관리에 관한 법률(허가)", exceptions) == ("excepted", "")
