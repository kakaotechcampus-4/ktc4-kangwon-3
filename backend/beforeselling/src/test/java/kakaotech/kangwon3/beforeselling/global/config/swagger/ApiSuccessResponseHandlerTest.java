package kakaotech.kangwon3.beforeselling.global.config.swagger;

import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.web.method.HandlerMethod;

import static org.assertj.core.api.Assertions.assertThat;

class ApiSuccessResponseHandlerTest {

    private final ApiSuccessResponseHandler handler = new ApiSuccessResponseHandler();

    @Test
    @DisplayName("기본 성공 응답은 200으로 공통 응답 본문과 함께 문서화된다")
    void documentsOkWithBody() throws Exception {
        // given
        Operation operation = new Operation().responses(new ApiResponses());

        // when
        handler.handleApiSuccessResponse(operation, handlerMethod("ok"));

        // then
        ApiResponse ok = operation.getResponses().get("200");
        assertThat(ok.getDescription()).isEqualTo("조회 성공");
        assertThat(ok.getContent().get("application/json").getSchema().getProperties())
                .containsKeys("code", "message", "data");
    }

    @Test
    @DisplayName("204 성공 응답은 본문 없이 문서화되고 기본 200 응답은 남지 않는다")
    void documentsNoContentWithoutBody() throws Exception {
        // given
        Operation operation = new Operation().responses(new ApiResponses().addApiResponse("200", new ApiResponse()));

        // when
        handler.handleApiSuccessResponse(operation, handlerMethod("noContent"));

        // then
        ApiResponse noContent = operation.getResponses().get("204");
        assertThat(noContent.getDescription()).isEqualTo("삭제 성공");
        assertThat(noContent.getContent()).isNull();
        assertThat(operation.getResponses()).doesNotContainKey("200");
    }

    private HandlerMethod handlerMethod(String name) throws NoSuchMethodException {
        return new HandlerMethod(new TestController(), TestController.class.getMethod(name));
    }

    static class TestController {

        @ApiResponseExplanations(success = @ApiSuccessResponseExplanation(description = "조회 성공"))
        public void ok() {
        }

        @ApiResponseExplanations(success = @ApiSuccessResponseExplanation(
                responseCode = CommonResponseCode.NO_CONTENT, description = "삭제 성공"))
        public void noContent() {
        }
    }
}
