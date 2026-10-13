"""국립전파연구원 적합성평가 외부 API 클라이언트."""

from .auth_info import RadioAuthInfoClient
from .auth_status import RadioAuthStatusClient

__all__ = [
    "RadioAuthInfoClient",
    "RadioAuthStatusClient",
]
