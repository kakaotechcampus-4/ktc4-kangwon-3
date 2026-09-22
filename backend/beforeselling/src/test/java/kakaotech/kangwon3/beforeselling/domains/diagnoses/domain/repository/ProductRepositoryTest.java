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
class ProductRepositoryTest {

    private static final Long USER_ID = 1L;
    private static final Long OTHER_USER_ID = 2L;
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    @DisplayName("상품을 이미지와 함께 조회하면 영속성 컨텍스트에서 분리된 뒤에도 이미지를 읽을 수 있다.")
    void findWithImagesById_thenImagesAreInitializedBeforeDetach() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));
        diagnoses.addProducts(List.of(product));
        Long productId = diagnosesRepository.save(diagnoses).getProducts().getFirst().getId();
        flushAndClear();

        // when
        Product found = productRepository.findWithImagesById(productId).orElseThrow();
        entityManager.detach(found);

        // then
        assertThat(found.getImages())
                .extracting(ProductImage::getImageKey)
                .containsExactly("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg");
    }

    @Test
    @DisplayName("마이페이지 목록을 조회하면 다른 사용자의 상품은 제외된다.")
    void search_thenExcludeOtherUsersProducts() {
        // given
        saveDiagnoses(USER_ID, "상품 A", "상품 B");
        saveDiagnoses(OTHER_USER_ID, "남의 상품");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, null, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(2);
        assertThat(result.getContent())
                .extracting(Product::getProductName)
                .containsExactlyInAnyOrder("상품 A", "상품 B");
    }

    @Test
    @DisplayName("진단서가 여러 개여도 사용자의 모든 상품이 하나의 목록으로 조회된다.")
    void search_acrossMultipleDiagnoses_thenReturnAllProducts() {
        // given
        saveDiagnoses(USER_ID, "상품 A", "상품 B");
        saveDiagnoses(USER_ID, "상품 C");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, null, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(3);
    }

    @Test
    @DisplayName("결과 필터를 지정하면 해당 결과의 상품만 조회된다.")
    void search_withResultStatus_thenReturnMatchingOnly() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(
                createProduct("재확인", ResultStatus.RECHECK_REQUIRED),
                createProduct("통과", ResultStatus.PURCHASING_AGENT_ALLOWED),
                createProduct("판정 전", null)));
        diagnosesRepository.save(diagnoses);
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(
                USER_ID, ResultStatus.RECHECK_REQUIRED, null, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
        assertThat(result.getContent().getFirst().getProductName()).isEqualTo("재확인");
    }

    @Test
    @DisplayName("상품명으로 검색하면 일부만 일치해도 조회된다.")
    void search_withKeyword_thenMatchPartially() {
        // given
        saveDiagnoses(USER_ID, "대나무 헬리콥터", "타임머신", "어디로든 문");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, "헬리", PageRequest.of(0, 10));

        // then
        assertThat(result.getContent())
                .extracting(Product::getProductName)
                .containsExactly("대나무 헬리콥터");
    }

    @Test
    @DisplayName("상품명 검색은 대소문자를 구분하지 않는다.")
    void search_withKeyword_thenIgnoreCase() {
        // given
        saveDiagnoses(USER_ID, "Bamboo Copter");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, "bamboo", PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
    }

    @Test
    @DisplayName("결과 필터와 검색어를 함께 지정하면 두 조건을 모두 만족하는 상품만 조회된다.")
    void search_withResultStatusAndKeyword_thenApplyBoth() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(
                createProduct("헬리콥터 재확인", ResultStatus.RECHECK_REQUIRED),
                createProduct("헬리콥터 통과", ResultStatus.PURCHASING_AGENT_ALLOWED),
                createProduct("타임머신 재확인", ResultStatus.RECHECK_REQUIRED)));
        diagnosesRepository.save(diagnoses);
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(
                USER_ID, ResultStatus.RECHECK_REQUIRED, "헬리콥터", PageRequest.of(0, 10));

        // then
        assertThat(result.getContent())
                .extracting(Product::getProductName)
                .containsExactly("헬리콥터 재확인");
    }

    @Test
    @DisplayName("목록을 최신순으로 조회하면 등록 시각 내림차순으로 반환된다.")
    void search_withLatestSort_thenSortByCreatedAtDescending() {
        // given
        saveDiagnoses(USER_ID, "상품 A", "상품 B", "상품 C");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, null,
                PageRequest.of(0, 10, Sort.by(Sort.Direction.DESC, "createdAt")));

        // then
        assertThat(result.getContent())
                .hasSize(3)
                .isSortedAccordingTo(Comparator.comparing(Product::getCreatedAt).reversed());
    }

    @Test
    @DisplayName("페이지 크기보다 상품이 많으면 다음 페이지가 있다고 응답한다.")
    void search_withSmallPageSize_thenHasNext() {
        // given
        saveDiagnoses(USER_ID, "상품 A", "상품 B", "상품 C");
        flushAndClear();

        // when
        Page<Product> result = productRepository.search(USER_ID, null, null, PageRequest.of(0, 2));

        // then
        assertThat(result.getContent()).hasSize(2);
        assertThat(result.getTotalElements()).isEqualTo(3);
        assertThat(result.getTotalPages()).isEqualTo(2);
        assertThat(result.hasNext()).isTrue();
    }

    private void saveDiagnoses(Long userId, String... productNames) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(List.of(productNames).stream()
                .map(name -> createProduct(name, null))
                .toList());
        diagnosesRepository.save(diagnoses);
    }

    private Product createProduct(String productName, ResultStatus resultStatus) {
        Product product = Product.pending(
                productName, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null);

        if (resultStatus != null) {
            ReflectionTestUtils.setField(product, "resultStatus", resultStatus);
        }
        return product;
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
