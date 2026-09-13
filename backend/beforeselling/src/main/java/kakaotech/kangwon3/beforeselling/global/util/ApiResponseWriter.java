package kakaotech.kangwon3.beforeselling.global.util;

import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 필터 체인 등 @RestControllerAdvice가 닿지 않는 곳에서 공통 응답 규격(ApiResponse)으로 실패 응답을 기록합니다.
 */
@Component
@RequiredArgsConstructor
public class ApiResponseWriter {

    private final JsonMapper jsonMapper;

    public void writeFail(HttpServletResponse response, BaseResponseCode responseCode) throws IOException {
        response.setStatus(responseCode.getStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(jsonMapper.writeValueAsString(ApiResponse.ofFail(responseCode)));
    }
}
