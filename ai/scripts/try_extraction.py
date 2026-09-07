"""수동 검증용 스크립트: 실제 상세페이지 텍스트·이미지로 ExtractionAgent를 돌려본다.

이 스크립트는 URL을 직접 호출하지 않는다. 알리·테무 같은 사이트는 서버가 직접 요청하면
차단되거나 일부만 내려주는 경우가 많다(1장 「입력 수집」 참고). 그래서 브라우저에서
Ctrl+A로 복사해 붙여넣은 텍스트와, 상세페이지 캡쳐 이미지를 파일로 받아서 쓴다.

사용법:
    cd ai
    cp .env.example .env  # OPENAI_API_KEY 채우기
    python scripts/try_extraction.py --text path/to/pasted.txt --image path/to/capture.png
"""

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.extraction import ExtractionAgent  # noqa: E402
from app.schemas.agent import ExtractionInput  # noqa: E402


def _image_to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def main() -> None:
    parser = argparse.ArgumentParser(description="ExtractionAgent 수동 검증")
    parser.add_argument(
        "--text", required=True, type=Path, help="상세페이지에서 복사해 붙여넣은 텍스트 파일"
    )
    parser.add_argument(
        "--image",
        action="append",
        type=Path,
        default=[],
        help="상세페이지 캡쳐 이미지 (여러 번 지정 가능)",
    )
    parser.add_argument("--product-id", default="manual-test-1")
    parser.add_argument("--source-url", default=None, help="출처 표시용 URL (선택)")
    args = parser.parse_args()

    source = ExtractionInput(
        product_id=args.product_id,
        source_url=args.source_url,
        text_blocks=[args.text.read_text(encoding="utf-8")],
        image_urls=[_image_to_data_uri(p) for p in args.image],
    )

    product = ExtractionAgent().extract(source)
    print(json.dumps(product.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
