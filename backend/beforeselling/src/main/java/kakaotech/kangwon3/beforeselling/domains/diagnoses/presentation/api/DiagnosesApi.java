package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;
import java.util.UUID;

@Tag(name = "Diagnoses", description = """
        상품 진단서 API.
        판매하려는 상품의 상세페이지 URL 또는 텍스트·이미지를 등록하면 진단 요청이 생성됩니다.
        생성과 동시에 AI 진단을 요청해 `IN_PROGRESS` 상태가 되며, AI 진단이 완료되어야 `resultStatus`와 `summary`가 채워집니다.
        """)
public interface DiagnosesApi {

    @Operation(
            summary = "신규 상품 진단 요청",
            description = """
                    상품 정보를 등록하고 AI에 진단을 요청합니다. 진단서와 상품은 `IN_PROGRESS` 상태로 저장됩니다.
                    `sourceType`이 `URL`이면 `sourceUrl`이 필수이고, `TEXT_IMAGE`이면 `sourceText`와 `imageKeys` 중 최소 하나가 필요합니다.
                    `imageKeys`와 `productImageKey`에는 Presigned URL 발급 응답의 `key`를 전달합니다(전체 URL 아님).
                    `productImageKey`는 목록 썸네일용 대표 이미지로, `sourceType`과 무관하게 선택 입력입니다.
                    응답으로 반환되는 `diagnosesId`로 이후 진행 상황을 조회합니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = DiagnosesCreateResponse.class, description = "진단 요청 생성 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
            }
    )
    ResponseEntity<ApiResponse<DiagnosesCreateResponse>> createDiagnoses(
            @Parameter(hidden = true) UserPrincipal principal,
            @Valid DiagnosesCreateRequest request);

    @Operation(
            summary = "상품 진단 단건 조회",
            description = """
                    진단서 한 건의 상세 정보를 조회합니다. 진단 진행 화면은 이 API를 주기적으로 다시 호출(숏폴링)해 갱신합니다.
                    등록 시 입력한 원본(`sourceText`, `imageUrls`)을 모두 포함합니다.
                    저장은 S3 key로 하지만 응답의 `imageUrls`와 `productImageUrl`은 접근 가능한 URL로 조립되어 내려갑니다.

                    **폴링**
                    - `pollIntervalMs`에 값이 있으면 그 간격(ms) 뒤에 다시 조회합니다. `null`이면 폴링을 멈춥니다.
                    - 대기·진행 중인 상품이 하나라도 있으면 값이 있습니다. 진단서 `processingStatus`가 `AWAITING_INPUT`이어도
                      다른 상품이 진행 중이면 값이 있으므로, 폴링 여부는 `processingStatus`가 아니라 `pollIntervalMs`로 판단합니다.
                    - 답변 대기 상품만 남으면 `null`입니다. 질문 답변 제출(`POST /api/v1/products/{productId}/answers`)이
                      성공하면 상품이 다시 진행 중이 되므로 그때 폴링을 다시 시작합니다.

                    **상품별 진행 정보** (`products[]`)
                    - `progresses`: 현재 실행의 단계·Tool별 진행 상태입니다. 단계 순서
                      (EXTRACTION → SELECTION → TOOL_EXECUTION → AGGREGATION → VERIFICATION → FINALIZATION)로 정렬되고,
                      같은 단계 안에서는 `toolName`이 없는 단계 자체의 행이 먼저, Tool은 `toolName` 순서로 옵니다.
                      진단이 끝나도 마지막 단계는 `STARTED`로 남을 수 있으므로, 화면에서는 상품의 `processingStatus`를 우선합니다.
                    - `questions`: 진단 중 받은 질문입니다. 회차·순서대로 모든 회차를 담고, 답변하기 전에는 `answerText`가 `null`입니다.
                    - `failure`: 상품이 `FAILED`일 때만 값이 있습니다. `retryable`이 `true`면 다시 진단하면 성공할 수 있습니다.

                    **진단 결과**
                    진단이 완료되면 상품마다 분야별 카드(`toolReviews`)와 그 안의 판단 항목(`findings`)·법령 근거(`legalSources`),
                    필요한 조치(`requiredActions`), 안내 사항(`notices`)이 함께 내려갑니다. 분야별 카드는 `toolName` 순서
                    (CUSTOMS → CHILDREN → ELECTRICAL → RADIO → FOOD_DRUG → LABEL_AD)로 정렬됩니다.
                    진단이 완료되지 않은 경우 `assessmentStatus`, `resultStatus`, `summary`는 `null`이고
                    `toolReviews`, `requiredActions`, `notices`는 빈 배열입니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = DiagnosesDetailResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<DiagnosesDetailResponse>> getDiagnoses(
            @Parameter(hidden = true) UserPrincipal principal,
            UUID diagnosesId);
}
