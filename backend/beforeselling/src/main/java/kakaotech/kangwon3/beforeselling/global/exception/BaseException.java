package kakaotech.kangwon3.beforeselling.global.exception;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import lombok.Getter;

@Getter
public class BaseException extends RuntimeException {

    private final BaseResponseCode responseCode;

    public BaseException(BaseResponseCode responseCode) {
        super(responseCode.getMessage());
        this.responseCode = responseCode;
    }
}
