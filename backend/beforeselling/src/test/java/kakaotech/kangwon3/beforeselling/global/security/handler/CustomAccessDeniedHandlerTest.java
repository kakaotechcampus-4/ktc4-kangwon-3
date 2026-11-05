package kakaotech.kangwon3.beforeselling.global.security.handler;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import tools.jackson.databind.json.JsonMapper;

import static org.assertj.core.api.Assertions.assertThat;

class CustomAccessDeniedHandlerTest {

    private final CustomAccessDeniedHandler handler = new CustomAccessDeniedHandler(
            new ApiResponseWriter(JsonMapper.builder().build()));

    @Test
    @DisplayName("권한이 없으면 403과 공통 응답 형식의 FORBIDDEN 코드를 응답한다.")
    void handle_thenForbiddenResponse() throws Exception {
        // given
        MockHttpServletResponse response = new MockHttpServletResponse();

        // when
        handler.handle(new MockHttpServletRequest(), response, new AccessDeniedException("denied"));

        // then
        assertThat(response.getStatus()).isEqualTo(403);
        assertThat(response.getContentType()).startsWith("application/json");
        assertThat(response.getContentAsString()).contains("\"code\":\"" + CommonResponseCode.FORBIDDEN.getCode() + "\"");
    }
}
