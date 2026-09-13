package kakaotech.kangwon3.beforeselling.global.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import kakaotech.kangwon3.beforeselling.global.config.swagger.ApiErrorResponseHandler;
import kakaotech.kangwon3.beforeselling.global.config.swagger.ApiSuccessResponseHandler;
import lombok.RequiredArgsConstructor;
import org.springdoc.core.customizers.OperationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.HandlerMethod;

/**
 * Swagger UI: /swagger-ui.html
 * 에러 코드 명세: /error-codes
 */
@Configuration
@RequiredArgsConstructor
public class SwaggerConfig {

    public static final String BEARER_AUTH = "bearerAuth";

    private final ApiSuccessResponseHandler apiSuccessResponseHandler;
    private final ApiErrorResponseHandler apiErrorResponseHandler;

    @Bean
    public OpenAPI openAPI() {
        SecurityScheme bearerScheme = new SecurityScheme()
                .type(SecurityScheme.Type.HTTP)
                .scheme("bearer")
                .bearerFormat("JWT")
                .in(SecurityScheme.In.HEADER)
                .name("Authorization");

        return new OpenAPI()
                .info(new Info()
                        .title("팔기전에 API")
                        .description("팔기전에(beforeselling) 백엔드 API 명세\n\n[📋 에러 코드 명세 보기](/error-codes)")
                        .version("v1"))
                .components(new Components().addSecuritySchemes(BEARER_AUTH, bearerScheme))
                .addSecurityItem(new SecurityRequirement().addList(BEARER_AUTH));
    }

    @Bean
    public OperationCustomizer operationCustomizer() {
        return (Operation operation, HandlerMethod handlerMethod) -> {
            apiSuccessResponseHandler.handleApiSuccessResponse(operation, handlerMethod);
            apiErrorResponseHandler.handleApiErrorResponse(operation, handlerMethod);
            return operation;
        };
    }
}
