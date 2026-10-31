"""app/db 밖에서는 app.db가 내보내는 것만 쓰는지(models·repositories 등 내부 모듈 직접 import 금지) 검증한다."""

import ast
from pathlib import Path

import app.db

APP = Path(__file__).resolve().parents[2] / "app"
# app.db가 __init__에서 내보내는 이름. from app.db import X에서 X가 이 밖이면 내부 모듈
PUBLIC = set(app.db.__all__)


def _imported_modules(path: Path) -> list[str]:
    """파일의 import 대상 모듈을 절대 이름으로 돌려준다. 상대 import는 파일 위치로 풀어 씀."""
    package = ["app", *path.relative_to(APP).parent.parts]
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[:len(package) - node.level + 1] if node.level else []
            module = ".".join([*base, *(node.module.split(".") if node.module else [])])
            names.append(module)
            # from app.db import models 처럼 하위 모듈을 이름으로 가져오는 경우
            names += [f"{module}.{alias.name}" for alias in node.names]
    return names


def test_app_db_밖에서는_app_db_내부_모듈을_import하지_않는다():
    violations = [
        f"{path.relative_to(APP.parent)}: {name}"
        for path in APP.rglob("*.py") if "db" not in path.relative_to(APP).parts[:1]
        for name in _imported_modules(path)
        if name.startswith("app.db.") and name.split(".")[2] not in PUBLIC
    ]

    assert violations == []


def test_상대_import도_절대_이름으로_풀어_검사한다():
    # main.py의 from .db import ... 가 app.db로 잡혀야 위 검사가 빈손으로 통과하지 않음
    names = _imported_modules(APP / "main.py")

    assert "app.db" in names
    assert "app.db.init_db" in names
