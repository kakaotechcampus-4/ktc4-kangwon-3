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

import java.util.List;

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
    public Page<Product> getProductList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        if (resultStatus == null) {
            return productRepository.findByDiagnosesUserId(userId, pageable);
        }
        return productRepository.findByDiagnosesUserIdAndResultStatus(userId, resultStatus, pageable);
    }

    /**
     * 상품 단건 삭제. 딸린 이미지는 cascade로 함께 삭제되고,
     * 진단서에 남은 상품이 없으면 진단서도 정리한다
     */
    @Transactional
    public void removeProduct(Long userId, Long productId) {
        Product product = productRepository.findWithImagesById(productId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        Diagnoses diagnoses = product.getDiagnoses();
        if (!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.FORBIDDEN);
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

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }

}
