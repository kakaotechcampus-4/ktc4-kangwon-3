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
                    AI 서버가 상품 하나의 진단 진행·질문·결과·실패를 알립니다. 종류는 본문의 `eventType`으로 구분합니다.

                    종류별 처리
                    - `product_progress`: 단계·Tool별 최신 진행 상태를 저장합니다. 상품 처리 상태는 바꾸지 않습니다.
                    - `product_awaiting_input`: 질문을 저장하고 상품을 답변 대기로 바꾼 뒤 진단서 상태를 다시 계산합니다.
                    - `product_result`: 상품을 완료 처리하고 결과 카드·판단·법령 근거·조치·안내를 저장한 뒤 진단서 상태를 다시 계산합니다.
                    - `product_failed`: 상품을 실패 처리하고 실패 단계·오류 정보를 저장한 뒤 진단서 상태를 다시 계산합니다.

                    공통 규칙
                    - 진단서 잠금을 기다리다 시간이 초과되면 `LOCK_CONFLICT`(COMMON-009)로 응답합니다. 다시 보내면 됩니다.
                    - 실행 식별자(runId)가 현재 실행과 다르거나 아직 저장 전이면 `LOCK_CONFLICT`(COMMON-009)로 응답합니다. 다시 보내면 됩니다.
                    - 진단서가 없거나 진단서와 상품 짝이 맞지 않으면 `NOT_FOUND`입니다.
                    - 처리할 수 없는 상태(아래 무시 조건 외)면 `CONFLICT`(COMMON-010)입니다. 다시 보내도 같은 결과입니다.

                    반영하지 않고 200으로 응답하는 경우(재전송·늦은 도착)
                    - 진행: 같은 실행에서 이미 반영한 것보다 앞선(또는 같은) `sequence`, 또는 이미 실패 처리된 상품
                    - 질문: 답변 대기 중인 상품에 이미 저장한 회차(`questionRound`)가 다시 온 경우
                    - 결과: 이미 결과가 반영된 상품
                    - 실패: 이미 실패 처리된 상품. 먼저 기록된 실패 정보를 유지합니다.

                    종류별 거절 조건
                    - 진행: `toolName`이 있는데 `stage`가 `tool_execution`이 아니면 `BAD_REQUEST`, 진단 중이 아니면(실패 제외) `CONFLICT`입니다.
                    - 질문: 한 이벤트 안에 같은 `questionKey`가 있으면 `BAD_REQUEST`, 이미 받은 회차 이하이거나 진단 중이 아니면 `CONFLICT`입니다.
                    - 결과: 진단 중이 아니면(완료 제외) `CONFLICT`, 같은 분야(`toolName`)의 카드가 중복되면 `DATA_INTEGRITY_VIOLATION`(COMMON-003)입니다.
                    - 실패: 진단 중이 아니면(실패 제외) `CONFLICT`입니다.
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
