package kakaotech.kangwon3.beforeselling.global.security.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 컨트롤러 메서드 파라미터에 붙여 인증된 사용자(UserPrincipal)를 주입받습니다.
 * 사용 예: {@code public ... method(@LoginUser UserPrincipal principal)}
 */
@Target(ElementType.PARAMETER)
@Retention(RetentionPolicy.RUNTIME)
public @interface LoginUser {
}
