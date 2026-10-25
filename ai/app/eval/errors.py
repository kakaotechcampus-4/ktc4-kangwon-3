"""평가 예외. 서비스 예외(AIError) 계열이 아님 (평가를 돌리는 사람이 보는 오류)."""


class RawFixtureMissing(FileNotFoundError):
    """원문 픽스처가 로컬에 없다. 저장소에는 축약본만 커밋된다."""


class InputsMismatch(ValueError):
    """로컬 입력 파일이 평가셋에 적힌 지문과 다르다. 다른 입력으로 잰 수치를 섞지 않게 막는다."""
