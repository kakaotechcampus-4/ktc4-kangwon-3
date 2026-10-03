"""화장품 규제성분·의료기기 Repository가 만드는 SQL을 DB 없이 검증한다."""

from app.repositories.fda import CosmeticIngredientRepository, MedicalDeviceRepository


def test_화장품_성분은_국문명_부분_일치로_검색한다(session):
    CosmeticIngredientRepository(session).search_by_name("하이드로")

    assert "cosmetic_ingredients.ingredient_name_ko LIKE '%%' || %(ingredient_name_ko_1)s || '%%'" in session.last_sql()


def test_의료기기는_품목분류번호로_조회한다(session):
    MedicalDeviceRepository(session).get_by_classification("A12345.01")

    assert "WHERE medical_devices.classification_no = %(classification_no_1)s" in session.last_sql()


def test_의료기기는_품목명_부분_일치로_검색한다(session):
    MedicalDeviceRepository(session).search_by_name("체온계")

    assert "medical_devices.product_name LIKE '%%' || %(product_name_1)s || '%%'" in session.last_sql()
