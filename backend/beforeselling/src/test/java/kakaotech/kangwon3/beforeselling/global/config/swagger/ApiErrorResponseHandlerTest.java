package kakaotech.kangwon3.beforeselling.global.config.swagger;

import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.headers.Header;
import io.swagger.v3.oas.models.responses.ApiResponses;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.web.method.HandlerMethod;

import static org.assertj.core.api.Assertions.assertThat;

class ApiErrorResponseHandlerTest {

    private final ApiErrorResponseHandler handler = new ApiErrorResponseHandler();

    @Test
    @DisplayName("인증이 필요한 API의 429 응답에는 다시 시도까지 남은 초를 알려주는 Retry-After 헤더가 문서화된다")
    void documentsRetryAfterHeaderOnTooManyRequests() throws Exception {
        // given
        Operation operation = new Operation().responses(new ApiResponses());

        // when
        handler.handleApiErrorResponse(operation, handlerMethod());

        // then
        Header retryAfter = operation.getResponses().get("429").getHeaders().get(HttpHeaders.RETRY_AFTER);
        assertThat(retryAfter).isNotNull();
        assertThat(retryAfter.getSchema().getType()).isEqualTo("integer");
    }

    @Test
    @DisplayName("429가 아닌 에러 응답에는 Retry-After 헤더를 붙이지 않는다")
    void doesNotDocumentRetryAfterOnOtherErrors() throws Exception {
        // given
        Operation operation = new Operation().responses(new ApiResponses());

        // when
        handler.handleApiErrorResponse(operation, handlerMethod());

        // then
        assertThat(operation.getResponses().get("401").getHeaders()).isNull();
    }

    private HandlerMethod handlerMethod() throws NoSuchMethodException {
        return new HandlerMethod(new TestController(), TestController.class.getMethod("authenticated"));
    }

    static class TestController {
        public void authenticated() {
        }
    }
}
