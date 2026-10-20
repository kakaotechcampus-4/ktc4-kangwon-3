package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.SortType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;
import java.util.UUID;

@Tag(name = "Products", description = """
        상품 API.
        진단서는 여러 상품을 한 번에 진단하기 위한 처리 단위이고, 사용자가 조회하고 삭제하는 대상은 상품입니다.
        마이페이지는 진단서가 아니라 상품 목록을 보여줍니다.
        """)
public interface ProductApi {

    @Operation(
            summary = "상품 목록 조회",
            description = """
                    로그인한 사용자가 지금까지 진단한 상품 목록을 조회합니다. (마이페이지)
                    여러 진단서에 걸친 상품이 하나의 목록으로 합쳐집니다.
                    `resultStatus`를 생략하면 전체를 조회하고, 지정하면 해당 결과의 상품만 조회합니다.
                    AI 진단 완료 전인 상품은 `resultStatus`가 없으므로 필터 지정 시 조회되지 않습니다.
                    `keyword`는 상품명 부분 일치로 검색하며 대소문자를 구분하지 않습니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = ProductListResponse.class, description = "조회 성공")
    )
    ResponseEntity<ApiResponse<ProductListResponse>> getProductList(
            @Parameter(hidden = true) UserPrincipal principal,
            @Parameter(description = "결과 필터. 생략하면 전체") ResultStatus resultStatus,
            @Parameter(description = "상품명 검색어. 생략하면 전체")
            @Size(max = 100, message = "검색어는 100자를 넘을 수 없습니다.") String keyword,
            @Parameter(description = "페이지 번호 (0부터)")
            @Min(value = 0, message = "페이지 번호는 0 이상이어야 합니다.") int page,
            @Parameter(description = "페이지 크기")
            @Min(value = 1, message = "페이지 크기는 1 이상이어야 합니다.")
            @Max(value = 100, message = "페이지 크기는 100 이하여야 합니다.") int size,
            @Parameter(description = "정렬 기준") SortType sortType);

    @Operation(
            summary = "상품 단건 조회",
            description = """
                    상품 하나의 진단 결과를 조회합니다. (마이페이지 → 상품 클릭)
                    응답은 진단서 단건 조회의 `products[]` 항목과 같은 형태입니다. 진행 중인 진단을 갱신할 때는 진단서 단건 조회를 폴링합니다.
                    저장은 S3 key로 하지만 응답의 `imageUrls`와 `productImageUrl`은 접근 가능한 URL로 조립되어 내려갑니다.

                    **진행 정보**
                    - `progresses`: 현재 실행의 단계·Tool별 진행 상태(단계 순서, 같은 단계에서는 단계 자체의 행이 먼저, Tool은 `toolName` 순서)
                    - `questions`: 진단 중 받은 질문과 답변(회차·순서대로 모든 회차)
                    - `failure`: 상품이 `FAILED`일 때만 실패 단계·오류 코드·메시지·재시도 가능 여부, 그 외에는 `null`

                    **진단 결과**
                    진단이 완료되면 분야별 카드(`toolReviews`)와 그 안의 판단 항목(`findings`)·법령 근거(`legalSources`),
                    필요한 조치(`requiredActions`), 안내 사항(`notices`)이 함께 내려갑니다. 분야별 카드는 `toolName` 순서
                    (CUSTOMS → CHILDREN → ELECTRICAL → RADIO → FOOD_DRUG → LABEL_AD)로 정렬됩니다.
                    진단이 완료되지 않은 경우 `assessmentStatus`, `resultStatus`, `summary`는 `null`이고
                    `toolReviews`, `requiredActions`, `notices`는 빈 배열입니다.
                    없는 상품과 다른 사용자의 상품은 모두 `NOT_FOUND`로 응답합니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = ProductResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<ProductResponse>> getProduct(
            @Parameter(hidden = true) UserPrincipal principal,
            UUID productId);

    @Operation(
            summary = "상품 단건 삭제",
            description = """
                    상품과 딸린 이미지를 함께 삭제합니다. 삭제된 데이터는 복구할 수 없습니다.
                    진단서에 남은 상품이 없으면 진단서도 함께 정리됩니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "삭제 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<Void>> removeProduct(
            @Parameter(hidden = true) UserPrincipal principal,
            UUID productId);
}
