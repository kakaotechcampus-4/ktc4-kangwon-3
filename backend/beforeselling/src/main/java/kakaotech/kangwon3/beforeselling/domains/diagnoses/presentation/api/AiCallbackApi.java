package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductEvent;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import org.springframework.http.ResponseEntity;

import java.util.UUID;

@Tag(name = "Internal - AI Callback", description = """
        AI 서버 전용 내부 API.
        모든 요청에 `X-Internal-Token` 헤더가 필요하며, Bearer 토큰으로는 호출할 수 없습니다.
        """)
public interface AiCallbackApi {

    @Operation(
            summary = "상품 진단 콜백 수신",
            description = """
                    AI 서버가 상품 하나의 진단 진행·결과를 알립니다. 종류는 본문의 `eventType`으로 구분합니다.

                    현재 처리하는 종류
                    - `product_result`: 진단 결과. 상품을 완료 처리하고 결과 카드·판단·법령 근거·조치·안내를 저장한 뒤 진단서 상태를 다시 계산합니다.
                    - `product_progress`, `product_awaiting_input`, `product_failed`는 아직 처리하지 않아 `BAD_REQUEST`로 거절합니다.

                    결과 콜백 처리 규칙
                    - 이미 결과가 반영된 상품에 결과가 다시 오면 반영하지 않고 200으로 응답합니다.
                    - 진단서 잠금을 기다리다 시간이 초과되면 `LOCK_CONFLICT`(COMMON-009)로 응답합니다. 다시 보내면 됩니다.
                    - 실행 식별자(runId)를 저장하기 전에 도착하면 `LOCK_CONFLICT`(COMMON-009)로 응답합니다. 다시 보내면 됩니다.
                    - 이전 실행(runId 불일치)의 결과는 반영하지 않고 200으로 응답합니다.
                    - 진단 중이 아닌 상품(대기, 답변 대기, 실패)이면 `CONFLICT`(COMMON-010)입니다.
                    - 같은 분야(`toolName`)의 카드가 중복되면 저장 단계에서 `DATA_INTEGRITY_VIOLATION`(COMMON-003)으로 거절됩니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "반영 성공(또는 반영하지 않고 무시)"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "BAD_REQUEST"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "DATA_INTEGRITY_VIOLATION"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "UNAUTHORIZED"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "LOCK_CONFLICT"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "CONFLICT"),
            }
    )
    // 사용자 Bearer 인증 대상이 아니므로 bearerAuth 요구와 AUTH-* 자동 예시를 붙이지 않는다.
    @SecurityRequirements
    ResponseEntity<ApiResponse<Void>> receiveCallback(
            @Parameter(description = "콜백 대상 상품 id. 처리는 본문의 productId 기준") UUID productId,
            @Valid ProductEvent event);
}
