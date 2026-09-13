package kakaotech.kangwon3.beforeselling.global.config.swagger;

import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.examples.Example;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.responses.ApiResponses;
import lombok.Builder;
import lombok.Getter;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class ApiErrorResponseHandler {

    /**
     * bearerAuth를 요구하는(= @SecurityRequirements로 공개 처리되지 않은) 모든 API에
     * 공통으로 발생 가능한 인증 에러. 매 API마다 개별 명시할 필요 없이 자동으로 401 응답에 추가된다.
     */
    private static final List<CommonAuthError> COMMON_AUTH_ERRORS = List.of(
            new CommonAuthError(CommonResponseCode.class, "UNAUTHORIZED"),
            new CommonAuthError(AuthResponseCode.class, "EXPIRED_ACCESS_TOKEN"),
            new CommonAuthError(AuthResponseCode.class, "INVALID_ACCESS_TOKEN")
    );

    public void handleApiErrorResponse(
            Operation operation,
            HandlerMethod handlerMethod
    ) {
        ApiResponseExplanations apiResponseExplanations = handlerMethod.getMethodAnnotation(ApiResponseExplanations.class);

        List<ExampleHolder> exampleHolders = new ArrayList<>();
        if (apiResponseExplanations != null) {
            Arrays.stream(apiResponseExplanations.errors())
                    .map(error -> createExampleHolder(error.exceptionCode(), error.name()))
                    .forEach(exampleHolders::add);
        }
        if (requiresAuthentication(operation)) {
            COMMON_AUTH_ERRORS.forEach(
                    error -> exampleHolders.add(createExampleHolder(error.exceptionCode(), error.name()))
            );
        }

        if (!exampleHolders.isEmpty()) {
            addExamplesToResponses(operation.getResponses(), exampleHolders);
        }
    }

    /**
     * 메서드에 {@code @SecurityRequirements}(빈 값)로 공개 처리되지 않은 API는
     * 전역 bearerAuth 요구 사항을 상속받는다. springdoc은 이 경우 operation에 security를
     * 별도로 채우지 않고 전역 설정 상속에 맡기므로, security가 null이면 인증이 필요한 API로 판단한다.
     */
    private boolean requiresAuthentication(Operation operation) {
        return operation.getSecurity() == null;
    }

    private void addExamplesToResponses(
            ApiResponses responses,
            List<ExampleHolder> exampleHolders
    ) {
        Map<Integer, List<ExampleHolder>> statusWithExampleHolders = exampleHolders.stream()
                .collect(Collectors.groupingBy(ExampleHolder::getHttpStatusCode));

        statusWithExampleHolders.forEach((status, holders) -> {
            Content content = new Content();
            MediaType mediaType = new MediaType();
            io.swagger.v3.oas.models.responses.ApiResponse apiResponse = new io.swagger.v3.oas.models.responses.ApiResponse();

            holders.forEach(
                    exampleHolder -> mediaType.addExamples(exampleHolder.getName(), exampleHolder.getHolder())
            );

            content.addMediaType("application/json", mediaType);
            apiResponse.setContent(content);
            responses.addApiResponse(String.valueOf(status), apiResponse);
        });
    }

    private ExampleHolder createExampleHolder(Class<? extends BaseResponseCode> enumClass, String targetName) {
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

    private record CommonAuthError(Class<? extends BaseResponseCode> exceptionCode, String name) {
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
