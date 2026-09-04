package kakaotech.kangwon3.beforeselling.global.annotation.swagger;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/* 성공 응답 형식 정의 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ApiSuccessResponseExplanation {

    CommonResponseCode responseCode() default CommonResponseCode.OK;

    Class<?> responseClass() default EmptyClass.class;

    String description() default "";

    class EmptyClass {
    }
}
