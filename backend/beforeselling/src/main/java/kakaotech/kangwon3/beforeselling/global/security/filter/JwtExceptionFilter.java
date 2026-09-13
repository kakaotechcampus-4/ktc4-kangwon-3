package kakaotech.kangwon3.beforeselling.global.security.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import lombok.RequiredArgsConstructor;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 필터 체인에서 발생한 BaseException(토큰 만료/변조 등)을 공통 응답 규격의 JSON으로 변환합니다.
 * 필터는 DispatcherServlet 바깥에서 실행되므로 @RestControllerAdvice가 처리하지 못합니다.
 */
@RequiredArgsConstructor
public class JwtExceptionFilter extends OncePerRequestFilter {

    private final ApiResponseWriter apiResponseWriter;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        try {
            filterChain.doFilter(request, response);
        } catch (BaseException e) {
            apiResponseWriter.writeFail(response, e.getResponseCode());
        }
    }
}
