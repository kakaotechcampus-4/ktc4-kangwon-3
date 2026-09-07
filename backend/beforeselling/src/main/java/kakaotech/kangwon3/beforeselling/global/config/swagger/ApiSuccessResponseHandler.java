package kakaotech.kangwon3.beforeselling.global.config.swagger;

import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;

import java.util.Map;

@Component
public class ApiSuccessResponseHandler {

    private static final String APPLICATION_JSON = "application/json";

    public void handleApiSuccessResponse(Operation operation, HandlerMethod handlerMethod) {
        ApiResponseExplanations apiResponseExplanations = handlerMethod.getMethodAnnotation(ApiResponseExplanations.class);

        if (apiResponseExplanations == null) {
            return;
        }

        ApiSuccessResponseExplanation apiSuccessResponseExplanation = apiResponseExplanations.success();

        ApiResponses responses = operation.getResponses();
        // 기본 200 OK 응답이 존재하면 제거
        responses.remove("200");

        Schema<?> responseSchema = new Schema<>()
                .addProperty("code", new Schema<>().example(apiSuccessResponseExplanation.responseCode().getCode()))
                .addProperty("message", new Schema<>().example(apiSuccessResponseExplanation.responseCode().getMessage()))
                .addProperty("data",
                        apiSuccessResponseExplanation.responseClass()
                                .isAssignableFrom(ApiSuccessResponseExplanation.EmptyClass.class)
                                ? new Schema<>().type("object").example(Map.of())
                                : new Schema<>().$ref(
                                        "#/components/schemas/" + apiSuccessResponseExplanation.responseClass().getSimpleName())
                );

        ApiResponse apiResponse = new ApiResponse()
                .description(apiSuccessResponseExplanation.description())
                .content(
                        new Content()
                                .addMediaType(
                                        APPLICATION_JSON,
                                        new MediaType().schema(responseSchema)
                                )
                );
        responses.addApiResponse(String.valueOf(apiSuccessResponseExplanation.responseCode().getStatus().value()), apiResponse);
    }
}
