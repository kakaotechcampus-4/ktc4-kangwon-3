package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductAnswerRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.ProductMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ProductUseCase {

    private final ProductService productService;
    private final ProductMapper productMapper;
    private final LawAmendmentService lawAmendmentService;

    public ProductListResponse getProductList(UUID userId, ResultStatus resultStatus,
                                              String keyword, Pageable pageable) {
        return productMapper.toListResponse(
                productService.getProductList(userId, resultStatus, keyword, pageable));
    }

    public void removeProduct(UUID userId, UUID productId) {
        productService.removeProduct(userId, productId);
    }

    public ProductResponse getProduct(UUID userId, UUID productId) {
        return productMapper.toResponse(
                productService.getProduct(userId, productId));
    }

    public void answerQuestions(UUID userId, UUID productId, ProductAnswerRequest request) {
        productService.answerQuestions(userId, productId, productMapper.toAnswers(request));
    }

    public void retryDiagnoses(UUID userId, UUID productId) {
        productService.retryDiagnoses(userId, productId);
    }

    // 재진단하면 결과가 새로 나오므로 재확인 대상에서 뺀다.
    public void rediagnoseProduct(UUID userId, UUID productId) {
        productService.rediagnoseProduct(userId, productId);
        lawAmendmentService.removeRecheckProducts(productId);
    }
}
