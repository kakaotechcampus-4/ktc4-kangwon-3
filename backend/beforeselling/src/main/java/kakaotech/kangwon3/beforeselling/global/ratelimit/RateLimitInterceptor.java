package kakaotech.kangwon3.beforeselling.global.ratelimit;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;

/**
 * 로그인 사용자별로 요청 수를 제한. 한도를 확인하지 못하면(Redis 장애 등) 요청을 통과
 */
@Slf4j
@RequiredArgsConstructor
public class RateLimitInterceptor implements HandlerInterceptor {

    private final RateLimiter rateLimiter;
    private final ApiResponseWriter apiResponseWriter;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws IOException {
        if (!(handler instanceof HandlerMethod handlerMethod)) {
            return true;
        }
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            return true;
        }

        RateLimitResult result;
        try {
            result = rateLimiter.tryConsume(policyOf(handlerMethod), principal.userId());
        } catch (RuntimeException e) {
            log.warn("처리율 제한 확인 실패, 요청을 통과시킵니다: {}", e.toString());
            return true;
        }

        if (result.allowed()) {
            return true;
        }
        response.setHeader(HttpHeaders.RETRY_AFTER, String.valueOf(result.retryAfterSeconds()));
        apiResponseWriter.writeFail(response, CommonResponseCode.TOO_MANY_REQUESTS);
        return false;
    }

    private RateLimitPolicy policyOf(HandlerMethod handlerMethod) {
        RateLimit rateLimit = handlerMethod.getMethodAnnotation(RateLimit.class);
        return rateLimit == null ? RateLimitPolicy.DEFAULT : rateLimit.value();
    }
}
