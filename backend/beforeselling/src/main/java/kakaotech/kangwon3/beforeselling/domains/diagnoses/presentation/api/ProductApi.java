package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesSortType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

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
            @Parameter(description = "상품명 검색어. 생략하면 전체") String keyword,
            @Parameter(description = "페이지 번호 (0부터)")
            @Min(value = 0, message = "페이지 번호는 0 이상이어야 합니다.") int page,
            @Parameter(description = "페이지 크기")
            @Min(value = 1, message = "페이지 크기는 1 이상이어야 합니다.")
            @Max(value = 100, message = "페이지 크기는 100 이하여야 합니다.") int size,
            @Parameter(description = "정렬 기준") DiagnosesSortType sortType);

    @Operation(
            summary = "상품 단건 삭제",
            description = """
                    상품과 딸린 이미지를 함께 삭제합니다. 삭제된 데이터는 복구할 수 없습니다.
                    진단서에 남은 상품이 없으면 진단서도 함께 정리됩니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(description = "삭제 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "FORBIDDEN"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<Void>> removeProduct(
            @Parameter(hidden = true) UserPrincipal principal,
            Long productId);
}
