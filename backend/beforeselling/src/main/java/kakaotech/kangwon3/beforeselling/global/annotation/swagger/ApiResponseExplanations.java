package kakaotech.kangwon3.beforeselling.global.annotation.swagger;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/* 성공, 예외 응답 정의 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ApiResponseExplanations {

    ApiSuccessResponseExplanation success() default @ApiSuccessResponseExplanation();

    ApiErrorResponseExplanation[] errors() default {};
}
