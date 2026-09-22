package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.ProductMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class ProductUseCase {

    private final ProductService productService;
    private final ProductMapper productMapper;

    public ProductListResponse getProductList(Long userId, ResultStatus resultStatus,
                                              String keyword, Pageable pageable) {
        return productMapper.toListResponse(
                productService.getProductList(userId, resultStatus, keyword, pageable));
    }

    public void removeProduct(Long userId, Long productId) {
        productService.removeProduct(userId, productId);
    }
}
