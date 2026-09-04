package kakaotech.kangwon3.beforeselling.global.common;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum CommonResponseCode implements BaseResponseCode {

    // 2xx Success
    OK(HttpStatus.OK, "OK", "요청이 성공적으로 처리되었습니다."),

    // 400 Bad Request
    BAD_REQUEST(HttpStatus.BAD_REQUEST, "COMMON-001", "잘못된 요청입니다."),
    INVALID_METHOD_ARGUMENT(HttpStatus.BAD_REQUEST, "COMMON-002", "올바르지 않은 요청 형식입니다."),
    DATA_INTEGRITY_VIOLATION(HttpStatus.BAD_REQUEST, "COMMON-003", "데이터 무결성 제약 조건을 위반하였습니다."),

    // 401 Unauthorized
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "COMMON-004", "인증이 필요합니다."),

    // 403 Forbidden
    FORBIDDEN(HttpStatus.FORBIDDEN, "COMMON-005", "요청 리소스에 대한 접근 권한이 없습니다."),

    // 404 Not Found
    NOT_FOUND(HttpStatus.NOT_FOUND, "COMMON-006", "요청 리소스를 찾을 수 없습니다."),

    // 405 Method Not Allowed
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "COMMON-007", "요청 메소드를 지원하지 않습니다."),

    // 500 Internal Server Error
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON-008", "서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
