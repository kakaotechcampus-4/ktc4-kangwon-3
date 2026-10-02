package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.SortType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.ProductUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api.ProductApi;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import java.util.UUID;

@RestController
@Validated
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController implements ProductApi {

    private final ProductUseCase productUseCase;

    // 마이페이지 상품 목록(결과 필터, 상품명 검색, 페이징, 정렬)
    @Override
    @GetMapping
    public ResponseEntity<ApiResponse<ProductListResponse>> getProductList(
            @LoginUser UserPrincipal principal,
            @RequestParam(required = false) ResultStatus resultStatus,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "LATEST") SortType sortType
    ) {
        // page/size 범위는 ProductApi 의 @Min/@Max 가 검증한다. 여기서 다시 보정하면
        // 규칙이 두 곳에 생겨 한쪽만 바뀔 때 어긋난다.
        Pageable pageable = PageRequest.of(page, size, sortType.getSort());
        ProductListResponse response =
                productUseCase.getProductList(principal.userId(), resultStatus, keyword, pageable);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, response));
    }

    // 상품 단건 삭제
    @Override
    @DeleteMapping("/{productId}")
    public ResponseEntity<ApiResponse<Void>> removeProduct(
            @LoginUser UserPrincipal principal,
            @PathVariable UUID productId
    ) {
        productUseCase.removeProduct(principal.userId(), productId);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
