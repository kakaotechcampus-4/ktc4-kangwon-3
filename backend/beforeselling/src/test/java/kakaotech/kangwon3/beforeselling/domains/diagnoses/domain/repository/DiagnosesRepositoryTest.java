package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.global.config.JpaAuditingConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.CryptoProperties;
import kakaotech.kangwon3.beforeselling.global.security.crypto.DatabaseEncryptionConverter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Comparator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({JpaAuditingConfig.class, DatabaseEncryptionConverter.class})
@EnableConfigurationProperties(CryptoProperties.class)
class DiagnosesRepositoryTest {

    private static final Long USER_ID = 1L;
    private static final Long OTHER_USER_ID = 2L;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    @DisplayName("진단서를 저장하면 등록 시각이 자동으로 기록된다.")
    void save_thenRecordCreatedAt() {
        // given & when
        Diagnoses saved = diagnosesRepository.save(createDiagnoses(USER_ID, null));

        // then
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();
    }

    @Test
    @DisplayName("진단서의 상품을 조회하면 요청한 순서대로 반환된다.")
    void findWithProductsById_thenReturnProductsInRequestOrder() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(
                createProduct("상품 A", null),
                createProduct("상품 B", null),
                createProduct("상품 C", null)));
        Long diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        List<Product> result = diagnosesRepository
                .findWithProductsByIdAndUserId(diagnosesId, USER_ID).orElseThrow().getProducts();

        // then
        assertThat(result)
                .extracting(Product::getProductName, Product::getSortOrder)
                .containsExactly(
                        org.assertj.core.api.Assertions.tuple("상품 A", 0),
                        org.assertj.core.api.Assertions.tuple("상품 B", 1),
                        org.assertj.core.api.Assertions.tuple("상품 C", 2));
    }

    @Test
    @DisplayName("상품의 이미지를 조회하면 업로드한 순서대로 반환된다.")
    void findWithProductsById_thenReturnImagesInUploadOrder() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.addImages(List.of(
                "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg", "product-detail/1/uuid_a3.jpg"));
        diagnoses.addProducts(List.of(product));
        Long diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        List<ProductImage> result = diagnosesRepository
                .findWithProductsByIdAndUserId(diagnosesId, USER_ID).orElseThrow()
                .getProducts().getFirst().getImages();

        // then
        assertThat(result)
                .extracting(ProductImage::getImageKey)
                .containsExactly(
                        "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg", "product-detail/1/uuid_a3.jpg");
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 빈 값이 반환된다.")
    void findWithProductsByIdAndUserId_withOtherUsersDiagnoses_thenReturnEmpty() {
        // given
        Long diagnosesId = diagnosesRepository.save(createDiagnoses(OTHER_USER_ID, null)).getId();
        flushAndClear();

        // when & then
        assertThat(diagnosesRepository.findWithProductsByIdAndUserId(diagnosesId, USER_ID)).isEmpty();
    }

    @Test
    @DisplayName("진단서를 삭제하면 딸린 상품과 이미지도 함께 제거되고 다른 진단서의 것은 남는다.")
    void delete_thenDeleteOnlyItsProductsAndImages() {
        // given
        Diagnoses target = Diagnoses.pending(USER_ID);
        Product targetProduct = createProduct("대나무 헬리콥터", null);
        targetProduct.addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));
        target.addProducts(List.of(targetProduct));
        Long targetId = diagnosesRepository.save(target).getId();

        Diagnoses other = Diagnoses.pending(USER_ID);
        Product otherProduct = createProduct("대나무 헬리콥터", null);
        otherProduct.addImages(List.of("product-detail/1/uuid_a9.jpg"));
        other.addProducts(List.of(otherProduct));
        Long otherId = diagnosesRepository.save(other).getId();
        flushAndClear();

        // when
        diagnosesRepository.delete(diagnosesRepository.findById(targetId).orElseThrow());
        flushAndClear();

        // then
        assertThat(countProducts()).isEqualTo(1);
        assertThat(countImages()).isEqualTo(1);
        assertThat(diagnosesRepository.findById(otherId).orElseThrow().getProducts()).hasSize(1);
    }

    @Test
    @DisplayName("사용자 탈퇴용으로 조회하면 해당 사용자의 모든 진단서를 상품과 함께 반환하고 다른 사용자의 것은 제외한다.")
    void findWithProductsByUserId_thenReturnAllDiagnosesWithProductsOfUser() {
        // given
        Diagnoses target1 = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.addImages(List.of("product-detail/1/uuid_a1.jpg"));
        target1.addProducts(List.of(product));
        diagnosesRepository.save(target1);

        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(OTHER_USER_ID, null));
        flushAndClear();

        // when
        List<Diagnoses> result = diagnosesRepository.findWithProductsByUserId(USER_ID);

        // then
        assertThat(result).hasSize(2);
        assertThat(result)
                .flatExtracting(Diagnoses::getProducts)
                .flatExtracting(Product::getImages)
                .extracting(ProductImage::getImageKey)
                .containsExactly("product-detail/1/uuid_a1.jpg");
    }

    @Test
    @DisplayName("마이페이지 목록을 조회하면 다른 사용자의 진단서는 제외된다.")
    void findByUserId_thenExcludeOtherUsersDiagnoses() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(OTHER_USER_ID, null));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(2);
        assertThat(result.getContent())
                .extracting(Diagnoses::getUserId)
                .containsOnly(USER_ID);
    }

    @Test
    @DisplayName("목록을 최신순으로 조회하면 등록 시각 내림차순으로 반환된다.")
    void findByUserId_withLatestSort_thenSortByCreatedAtDescending() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        flushAndClear();

        PageRequest pageRequest = PageRequest.of(0, 10, Sort.by(Sort.Direction.DESC, "createdAt"));

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, pageRequest);

        // then
        assertThat(result.getContent())
                .hasSize(3)
                .isSortedAccordingTo(Comparator.comparing(Diagnoses::getCreatedAt).reversed());
    }

    @Test
    @DisplayName("페이지 크기보다 진단서가 많으면 다음 페이지가 있다고 응답한다.")
    void findByUserId_withSmallPageSize_thenHasNext() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, PageRequest.of(0, 2));

        // then
        assertThat(result.getContent()).hasSize(2);
        assertThat(result.getTotalElements()).isEqualTo(3);
        assertThat(result.getTotalPages()).isEqualTo(2);
        assertThat(result.hasNext()).isTrue();
    }

    @Test
    @DisplayName("결과 필터로 목록을 조회하면 해당 결과의 상품을 가진 진단서만 반환된다.")
    void findByUserIdAndProductResultStatus_thenReturnMatchingOnly() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.RECHECK_REQUIRED));
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.PURCHASING_AGENT_ALLOWED));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserIdAndProductResultStatus(
                USER_ID, ResultStatus.RECHECK_REQUIRED, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
        assertThat(result.getContent().getFirst().getProducts())
                .extracting(Product::getResultStatus)
                .containsOnly(ResultStatus.RECHECK_REQUIRED);
    }

    @Test
    @DisplayName("결과 필터로 목록을 조회하면 진단이 완료되지 않은 진단서는 조회되지 않는다.")
    void findByUserIdAndProductResultStatus_thenExcludePendingDiagnoses() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.RECHECK_REQUIRED));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserIdAndProductResultStatus(
                USER_ID, ResultStatus.RECHECK_REQUIRED, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
    }

    @Test
    @DisplayName("같은 결과의 상품을 여러 개 가진 진단서도 목록에 한 번만 나타난다.")
    void findByUserIdAndProductResultStatus_withDuplicatedResults_thenReturnDistinctDiagnoses() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(
                createProduct("상품 A", ResultStatus.RECHECK_REQUIRED),
                createProduct("상품 B", ResultStatus.RECHECK_REQUIRED)));
        diagnosesRepository.save(diagnoses);
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserIdAndProductResultStatus(
                USER_ID, ResultStatus.RECHECK_REQUIRED, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
        assertThat(result.getContent()).hasSize(1);
    }

    private Diagnoses createDiagnoses(Long userId, ResultStatus resultStatus) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(List.of(createProduct("대나무 헬리콥터", resultStatus)));
        return diagnoses;
    }

    private Product createProduct(String productName, ResultStatus resultStatus) {
        Product product = Product.pending(
                productName,
                "product-main/1/uuid_thumbnail.jpg",
                SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491",
                null);

        if (resultStatus != null) {
            ReflectionTestUtils.setField(product, "resultStatus", resultStatus);
        }
        return product;
    }

    private long countProducts() {
        return entityManager.createQuery("select count(p) from Product p", Long.class).getSingleResult();
    }

    private long countImages() {
        return entityManager.createQuery("select count(i) from ProductImage i", Long.class).getSingleResult();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
