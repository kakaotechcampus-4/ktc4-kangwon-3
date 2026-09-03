package kakaotech.kangwon3.beforeselling.global.security.resolver;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.core.MethodParameter;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

/**
 * {@code @LoginUser} 파라미터에 SecurityContext의 인증 주체를 주입합니다.
 * JwtAuthenticationFilter가 이미 SecurityContext를 채워두므로 DB 조회 없이 즉시 반환합니다.
 * anyRequest().authenticated() 정책상 인증 안 된 요청은 이 리졸버까지 도달하지 않지만, 방어적으로 한 번 더 검증합니다.
 */
@Component
public class LoginUserArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return parameter.hasParameterAnnotation(LoginUser.class)
                && UserPrincipal.class.equals(parameter.getParameterType());
    }

    @Override
    public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                                  NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            throw new BaseException(CommonResponseCode.UNAUTHORIZED);
        }
        return principal;
    }
}
