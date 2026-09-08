package kakaotech.kangwon3.beforeselling.global.annotation.swagger;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/* 예외 응답 정의 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ApiErrorResponseExplanation {

    Class<? extends BaseResponseCode> exceptionCode();

    String name();
}
