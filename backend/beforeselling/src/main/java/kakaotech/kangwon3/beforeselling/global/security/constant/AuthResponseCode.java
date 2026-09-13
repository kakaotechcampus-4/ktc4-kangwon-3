package kakaotech.kangwon3.beforeselling.global.security.constant;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

/**
 * 인증 도메인 전용 응답 코드.
 * 프론트엔드가 코드 기반으로 분기(토큰 만료 시 재발급, 리프레시 토큰 무효 시 재로그인 등)해야 하는 경우에만 정의합니다.
 */
@Getter
@RequiredArgsConstructor
public enum AuthResponseCode implements BaseResponseCode {

    // 401 Unauthorized
    EXPIRED_ACCESS_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH-001", "액세스 토큰이 만료되었습니다."),
    INVALID_ACCESS_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH-002", "유효하지 않은 액세스 토큰입니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH-003", "유효하지 않은 리프레시 토큰입니다."),
    OAUTH2_LOGIN_FAILED(HttpStatus.UNAUTHORIZED, "AUTH-004", "소셜 로그인에 실패했습니다."),

    // 400 Bad Request
    UNSUPPORTED_SOCIAL_PROVIDER(HttpStatus.BAD_REQUEST, "AUTH-005", "지원하지 않는 소셜 로그인 제공자입니다."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
