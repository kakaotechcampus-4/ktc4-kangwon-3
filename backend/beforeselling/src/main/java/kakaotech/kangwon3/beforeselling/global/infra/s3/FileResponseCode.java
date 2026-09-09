package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum FileResponseCode implements BaseResponseCode {

    // 400 Bad Request
    NOT_SUPPORTED_EXTENSION(HttpStatus.BAD_REQUEST, "FILE-001", "지원되지 않는 파일 확장자입니다."),
    NOT_SUPPORTED_CONTENT_TYPE(HttpStatus.BAD_REQUEST, "FILE-002", "파일 확장자와 일치하지 않는 Content-Type입니다."),
    EXCEED_FILE_SIZE(HttpStatus.BAD_REQUEST, "FILE-003", "파일 크기가 허용 용량을 초과했습니다."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
