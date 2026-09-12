package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesSortType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

@Tag(name = "Diagnoses", description = """
        상품 진단서 API.
        판매하려는 상품의 상세페이지 URL 또는 텍스트·이미지를 등록하면 진단 요청이 생성됩니다.
        생성 직후에는 `PENDING` 상태이며, AI 진단이 완료되어야 `resultStatus`와 `summary`가 채워집니다.
        """)
public interface DiagnosesApi {

    @Operation(
            summary = "신규 상품 진단 요청",
            description = """
                    상품 정보를 등록하고 진단 요청을 생성합니다. 진단서는 `PENDING` 상태로 저장됩니다.
                    `sourceType`이 `URL`이면 `sourceUrl`이 필수이고, `TEXT_IMAGE`이면 `sourceText`와 `imageUrls` 중 최소 하나가 필요합니다.
                    `productImageUrl`은 목록 썸네일용 대표 이미지로, `sourceType`과 무관하게 선택 입력입니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "진단 요청 생성 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
            }
    )
    ResponseEntity<ApiResponse<Void>> createDiagnoses(
            @Parameter(hidden = true) UserPrincipal principal,
            @Valid DiagnosesCreateRequest request);

    @Operation(
            summary = "상품 진단 단건 조회",
            description = """
                    진단서 한 건의 상세 정보를 조회합니다. 등록 시 입력한 원본(`sourceText`, `imageUrls`)을 모두 포함합니다.
                    진단이 완료되지 않은 경우 `resultStatus`와 `summary`는 `null`입니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = DiagnosesDetailResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "FORBIDDEN"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<DiagnosesDetailResponse>> getDiagnoses(
            @Parameter(hidden = true) UserPrincipal principal,
            Long diagnosesId);

    @Operation(
            summary = "상품 진단 목록 조회",
            description = """
                    로그인한 사용자의 진단서 목록을 조회합니다. (마이페이지)
                    `resultStatus`를 생략하면 전체를 조회하고, 지정하면 해당 결과의 진단서만 조회합니다.
                    AI 진단 완료 전인 진단서는 `resultStatus`가 없으므로 필터 지정 시 조회되지 않습니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = DiagnosesListResponse.class, description = "조회 성공")
    )
    ResponseEntity<ApiResponse<DiagnosesListResponse>> getDiagnosesList(
            @Parameter(hidden = true) UserPrincipal principal,
            @Parameter(description = "결과 필터. 생략하면 전체") ResultStatus resultStatus,
            @Parameter(description = "페이지 번호 (0부터)") @Min(0) int page,
            @Parameter(description = "페이지 크기") @Min(1) @Max(100) int size,
            @Parameter(description = "정렬 기준") DiagnosesSortType sortType);

    @Operation(
            summary = "상품 진단 단건 삭제",
            description = "진단서와 딸린 이미지를 함께 삭제합니다. 삭제된 데이터는 복구할 수 없습니다.")
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "삭제 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "FORBIDDEN"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<Void>> removeDiagnoses(
            @Parameter(hidden = true) UserPrincipal principal,
            Long diagnosesId);
}
