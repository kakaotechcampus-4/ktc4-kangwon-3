package kakaotech.kangwon3.beforeselling.global.security.constant;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum DiagnosesResponseCode implements BaseResponseCode {

    // 403 Forbidden
    DIAGNOSES_ACCESS_DENIED(HttpStatus.FORBIDDEN, "DIAGNOSES-001", "해당 진단서에 대한 접근 권한이 없습니다."),

    // 404 Not Found
    DIAGNOSES_NOT_FOUND(HttpStatus.NOT_FOUND, "DIAGNOSES-002", "진단서를 찾을 수 없습니다."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
