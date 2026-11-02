package kakaotech.kangwon3.beforeselling.global.ratelimit;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 컨트롤러 메서드에 적용할 처리율 제한 정책. 붙이지 않으면 기본값 {@link RateLimitPolicy#DEFAULT} 적용
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface RateLimit {

    RateLimitPolicy value();
}
