package kakaotech.kangwon3.beforeselling.global.security.handler;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;

/**
 * 인증은 되었지만 권한이 없는 경우(403) 공통 응답 규격으로 응답합니다.
 */
@RequiredArgsConstructor
public class CustomAccessDeniedHandler implements AccessDeniedHandler {

    private final ApiResponseWriter apiResponseWriter;

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                       AccessDeniedException accessDeniedException) throws IOException {
        apiResponseWriter.writeFail(response, CommonResponseCode.FORBIDDEN);
    }
}
