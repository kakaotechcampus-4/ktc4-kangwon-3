package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import org.springframework.http.ResponseEntity;

@Tag(name = "Internal - AI Callback", description = """
        AI 서버 전용 내부 API.
        모든 요청에 `X-Internal-Token` 헤더가 필요하며, Bearer 토큰으로는 호출할 수 없습니다.
        """)
public interface LawAmendmentCallbackApi {

    @Operation(
            summary = "법령 변경 콜백 수신",
            description = """
                    AI 서버가 매일 법령 점검에서 찾은 진단 근거 법령의 변경(근거로 쓰는 판이 바뀐 것)을 한 번에 알립니다.

                    처리
                    - 변경을 저장합니다. 같은 변경(`documentId`·`serialNumber`)을 다시 받으면 저장하지 않고 200으로 응답합니다.
                    - 그 분야(`toolName`) 검토에서 이 법령을 근거로 인용한(진단 결과 근거의 `lawName`이 같은) 상품을 재확인 대상으로 지정하고,
                      개정 알림을 켠 회원에게 메일을 보냅니다. 변경이 여러 건이어도 회원당 한 통으로 묶어 보냅니다.
                      메일은 반영이 끝난 뒤 따로 보내므로 발송 결과는 응답에 영향을 주지 않습니다.

                    거절 조건
                    - 필수 값이 없거나 길이를 넘으면 `INVALID_METHOD_ARGUMENT`, 본문 형식이나 enum 값이 맞지 않으면 `BAD_REQUEST`입니다.
                    - 같은 변경이 동시에 들어와 저장이 겹치면 `DATA_INTEGRITY_VIOLATION`(COMMON-003)이고 그 요청은 반영하지 않습니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "반영 성공(또는 이미 받은 변경이라 무시)"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "BAD_REQUEST"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "DATA_INTEGRITY_VIOLATION"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "UNAUTHORIZED"),
            }
    )
    @SecurityRequirements
    ResponseEntity<ApiResponse<Void>> receiveLawChanges(@Valid LawChangeCallbackRequest request);
}
