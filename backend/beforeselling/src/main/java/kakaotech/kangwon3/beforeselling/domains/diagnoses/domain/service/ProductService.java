package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

    private final ProductRepository productRepository;
    private final DiagnosesRepository diagnosesRepository;
    private final ApplicationEventPublisher eventPublisher;

    /**
     * 마이페이지 상품 목록. 진단서가 아니라 상품 단위로 조회한다.
     */
    public Page<Product> getProductList(UUID userId, ResultStatus resultStatus,
                                        String keyword, Pageable pageable) {
        return productRepository.search(userId, resultStatus, normalizeKeyword(keyword), pageable);
    }

    /**
     * 상품 단건 삭제. 딸린 이미지는 cascade로 함께 삭제되고,
     * 진단서에 남은 상품이 없으면 진단서도 정리한다
     */
    @Transactional
    public void removeProduct(UUID userId, UUID productId) {
        Product product = productRepository.findWithImagesById(productId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        Diagnoses diagnoses = product.getDiagnoses();
        // 타인 소유 리소스도 404로 응답한다. 403을 주면 해당 id가 존재한다는 사실이
        // 노출되어 ID 탐색에 악용될 수 있다(CODE_CONVENTION.md 참고).
        if (!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.NOT_FOUND);
        }

        List<String> imageKeys = product.collectImageKeys();

        diagnoses.removeProduct(product);

        boolean diagnosesRemoved = diagnoses.isEmpty();
        if (diagnosesRemoved) {
            diagnosesRepository.delete(diagnoses);
        }

        publishDeleteEvent(imageKeys);

        log.debug("상품 삭제 완료. productId={}, userId={}, 진단서 함께 삭제={}",
                productId, userId, diagnosesRemoved);
    }

    // 빈 문자열로 들어온 검색어는 "검색하지 않음"으로 취급한다.
    private String normalizeKeyword(String keyword) {
        return StringUtils.hasText(keyword) ? keyword.trim() : null;
    }

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }

}
