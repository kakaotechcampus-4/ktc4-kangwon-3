package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

    private final ProductRepository productRepository;
    private final S3FileService s3FileService;
    private final ApplicationEventPublisher eventPublisher;

    // 상품 + 이미지 저장(이미지는 cascade로 함께 저장된다)
    @Transactional
    public Product createProduct(ProductCreateCommand command) {
        Product product = Product.pending(
                command.userId(),
                command.productName(),
                command.productImageKey(),
                command.sourceType(),
                command.sourceUrl(),
                command.sourceText()
        );
        product.addImages(command.imageKeys());

        s3FileService.markConfirmed(collectImageKeys(product));
        Product saved = productRepository.save(product);
        log.debug("상품 생성 완료. productId={}, userId={}", saved.getId(), command.userId());

        return saved;
    }

    // 단건 조회 + 소유권 검증
    public Product getProduct(Long userId, Long productId) {
        Product product = productRepository.findWithImagesById(productId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        if(!product.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.FORBIDDEN);
        }
        return product;
    }

    // 목록 조회, 필터 유무 분기
    public Page<Product> getProductList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        if(resultStatus == null) {
            return productRepository.findByUserId(userId, pageable);
        }
        return productRepository.findByUserIdAndResultStatus(userId, resultStatus, pageable);
    }

    // 상품 삭제(딸린 이미지는 cascade로 함께 삭제)
    @Transactional
    public void removeProduct(Long userId, Long productId) {
        Product product = getProduct(userId, productId);
        List<String> imageKeys = collectImageKeys(product);
        productRepository.delete(product);
        publishDeleteEvent(imageKeys);

        log.debug("상품 삭제 완료. productId={}, userId={}", productId, userId);
    }

    // 회원 탈퇴 시 해당 사용자의 모든 상품 이미지에 대한 S3 삭제 요청
    @Transactional
    public void removeAllByUserId(Long userId) {
        List<Product> productList = productRepository.findWithImagesByUserId(userId);

        List<String> imageKeys = productList.stream()
                .flatMap(product -> collectImageKeys(product).stream())
                .toList();

        productRepository.deleteAll(productList);
        publishDeleteEvent(imageKeys);

        log.debug("회원 탈퇴에 따른 상품 삭제 완료. userId={}, 상품 수={}, 대상 key 수={}",
                userId, productList.size(), imageKeys.size());
    }

    private List<String> collectImageKeys(Product product) {
        List<String> keys = new ArrayList<>();
        if (product.getProductImageKey() != null) {
            keys.add(product.getProductImageKey());
        }
        product.getImages().stream().map(ProductImage::getImageKey).forEach(keys::add);
        return keys;
    }

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }
}
