package kakaotech.kangwon3.beforeselling.global.config.swagger;

import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.examples.Example;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.responses.ApiResponses;
import lombok.Builder;
import lombok.Getter;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class ApiErrorResponseHandler {

    public void handleApiErrorResponse(
            Operation operation,
            HandlerMethod handlerMethod
    ) {
        ApiResponseExplanations apiResponseExplanations = handlerMethod.getMethodAnnotation(ApiResponseExplanations.class);

        if (apiResponseExplanations != null) {
            generateResponseCodeResponseExample(operation, Arrays.asList(apiResponseExplanations.errors()));
        }
    }

    private void generateResponseCodeResponseExample(
            Operation operation,
            List<ApiErrorResponseExplanation> apiErrorResponseExplanations
    ) {
        ApiResponses responses = operation.getResponses();

        Map<Integer, List<ExampleHolder>> statusWithExampleHolders = apiErrorResponseExplanations.stream()
                .map(this::createExampleHolder)
                .collect(Collectors.groupingBy(ExampleHolder::getHttpStatusCode));

        addExamplesToResponses(responses, statusWithExampleHolders);
    }

    private ExampleHolder createExampleHolder(ApiErrorResponseExplanation apiErrorResponseExplanation) {
        Class<? extends BaseResponseCode> enumClass = apiErrorResponseExplanation.exceptionCode();
        String targetName = apiErrorResponseExplanation.name();

        BaseResponseCode[] codes = enumClass.getEnumConstants();

        return Arrays.stream(codes)
                .filter(code -> ((Enum<?>) code).name().equals(targetName))
                .findFirst()
                .map(responseCode -> ExampleHolder.builder()
                        .httpStatusCode(responseCode.getStatus().value())
                        .name(((Enum<?>) responseCode).name())
                        .errorCode(responseCode.getCode())
                        .description(responseCode.getMessage())
                        .holder(createSwaggerExample(responseCode, responseCode.getMessage()))
                        .build())
                .orElseThrow(() -> new IllegalArgumentException(
                        enumClass.getSimpleName() + "에 '" + targetName + "' 상수가 존재하지 않습니다. "
                                + "@ApiErrorResponseExplanation의 name 값을 확인하세요."));
    }

    private Example createSwaggerExample(BaseResponseCode responseCode, String description) {
        ApiResponse<Object> apiResponse = ApiResponse.ofFail(responseCode);

        Example example = new Example();
        example.setValue(apiResponse);
        example.setDescription(description);

        return example;
    }

    private void addExamplesToResponses(
            ApiResponses responses,
            Map<Integer, List<ExampleHolder>> statusWithExampleHolders
    ) {
        statusWithExampleHolders.forEach((status, exampleHolders) -> {
            Content content = new Content();
            MediaType mediaType = new MediaType();
            io.swagger.v3.oas.models.responses.ApiResponse apiResponse = new io.swagger.v3.oas.models.responses.ApiResponse();

            exampleHolders.forEach(
                    exampleHolder -> mediaType.addExamples(exampleHolder.getName(), exampleHolder.getHolder())
            );

            content.addMediaType("application/json", mediaType);
            apiResponse.setContent(content);
            responses.addApiResponse(String.valueOf(status), apiResponse);
        });
    }

    @Getter
    @Builder
    private static class ExampleHolder {
        private final int httpStatusCode;
        private final String name;
        private final String errorCode;
        private final String description;
        private final Example holder;
    }
}
