package kakaotech.kangwon3.beforeselling.global.common;

import org.springframework.http.HttpStatus;

public interface BaseResponseCode {

    HttpStatus getStatus();
    String getCode();
    String getMessage();
}
