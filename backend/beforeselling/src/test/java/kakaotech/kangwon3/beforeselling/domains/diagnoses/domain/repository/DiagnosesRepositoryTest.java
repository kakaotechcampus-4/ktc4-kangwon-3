package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AgentReview;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AgentReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AgentType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductQuestion;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
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
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.UUID;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({JpaAuditingConfig.class, DatabaseEncryptionConverter.class})
@EnableConfigurationProperties(CryptoProperties.class)
class DiagnosesRepositoryTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();

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
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        List<Product> result = diagnosesRepository
                .findWithProductsById(diagnosesId).orElseThrow().getProducts();

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
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        List<ProductImage> result = diagnosesRepository
                .findWithProductsById(diagnosesId).orElseThrow()
                .getProducts().getFirst().getImages();

        // then
        assertThat(result)
                .extracting(ProductImage::getImageKey)
                .containsExactly(
                        "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg", "product-detail/1/uuid_a3.jpg");
    }

    @Test
    @DisplayName("진단서를 삭제하면 딸린 상품과 이미지도 함께 제거되고 다른 진단서의 것은 남는다.")
    void delete_thenDeleteOnlyItsProductsAndImages() {
        // given
        Diagnoses target = Diagnoses.pending(USER_ID);
        Product targetProduct = createProduct("대나무 헬리콥터", null);
        targetProduct.addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));
        target.addProducts(List.of(targetProduct));
        UUID targetId = diagnosesRepository.save(target).getId();

        Diagnoses other = Diagnoses.pending(USER_ID);
        Product otherProduct = createProduct("대나무 헬리콥터", null);
        otherProduct.addImages(List.of("product-detail/1/uuid_a9.jpg"));
        other.addProducts(List.of(otherProduct));
        UUID otherId = diagnosesRepository.save(other).getId();
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
    @DisplayName("본인의 진단서를 잠금 조회하면 진단서가 반환된다.")
    void findByIdAndUserIdForUpdate_withOwner_thenReturnDiagnoses() {
        // given
        UUID diagnosesId = diagnosesRepository.save(createDiagnoses(USER_ID, null)).getId();
        flushAndClear();

        // when
        Optional<Diagnoses> result = diagnosesRepository.findByIdAndUserIdForUpdate(diagnosesId, USER_ID);

        // then
        assertThat(result).isPresent();
        assertThat(result.get().getProducts()).hasSize(1);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 잠금 조회하면 빈 결과가 반환된다.")
    void findByIdAndUserIdForUpdate_withOtherUser_thenReturnEmpty() {
        // given
        UUID diagnosesId = diagnosesRepository.save(createDiagnoses(OTHER_USER_ID, null)).getId();
        flushAndClear();

        // when
        Optional<Diagnoses> result = diagnosesRepository.findByIdAndUserIdForUpdate(diagnosesId, USER_ID);

        // then
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("상품의 에이전트 카드와 질문은 상품과 함께 저장되고, 질문은 질문 순서대로 조회된다.")
    void save_thenPersistAgentReviewsAndQuestionsInOrder() {
        // given: 질문을 순서와 반대로 추가한다.
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.recordAgentReview(AgentType.INTAKE, AgentReviewStatus.COMPLETED, "상세페이지를 인식했습니다.");
        product.recordAgentReview(AgentType.FOOD_DRUG, AgentReviewStatus.SKIPPED, "식품 접촉 항목이 없습니다.");
        product.askQuestions(List.of(
                new QuestionContent("target_age", 2, "실제로 주로 판매하는 대상 연령은?", null),
                new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null)));
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Product saved = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();

        // then
        assertThat(saved.getAgentReviews())
                .extracting(AgentReview::getAgentType)
                .containsExactlyInAnyOrder(AgentType.INTAKE, AgentType.FOOD_DRUG);
        assertThat(saved.getQuestions())
                .extracting(ProductQuestion::getQuestionKey)
                .containsExactly("sales_type", "target_age");
    }

    @Test
    @DisplayName("저장된 카드와 같은 에이전트의 카드를 다시 기록하면 행이 늘지 않고 내용만 바뀐다.")
    void recordAgentReview_afterReload_thenUpdateWithoutNewRow() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.recordAgentReview(AgentType.CUSTOMS, AgentReviewStatus.FAILED, "조회에 실패했습니다.");
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst()
                .recordAgentReview(AgentType.CUSTOMS, AgentReviewStatus.COMPLETED, "세관장확인 요건이 없습니다.");
        flushAndClear();

        // then
        assertThat(countAgentReviews()).isEqualTo(1);
        assertThat(entityManager.createQuery("select r from AgentReview r", AgentReview.class).getSingleResult())
                .extracting(AgentReview::getStatus, AgentReview::getDescription)
                .containsExactly(AgentReviewStatus.COMPLETED, "세관장확인 요건이 없습니다.");
    }

    @Test
    @DisplayName("진단서를 삭제하면 상품의 카드와 질문도 함께 제거되고 다른 진단서의 것은 남는다.")
    void delete_thenDeleteOnlyItsAgentReviewsAndQuestions() {
        // given
        UUID targetId = diagnosesRepository.save(createDiagnosesWithReviewAndQuestion()).getId();
        UUID otherId = diagnosesRepository.save(createDiagnosesWithReviewAndQuestion()).getId();
        flushAndClear();

        // when
        diagnosesRepository.delete(diagnosesRepository.findById(targetId).orElseThrow());
        flushAndClear();

        // then
        assertThat(countAgentReviews()).isEqualTo(1);
        assertThat(countQuestions()).isEqualTo(1);
        assertThat(diagnosesRepository.findById(otherId)).isPresent();
    }

    @Test
    @DisplayName("진단서에서 상품을 제거하면 그 상품의 카드와 질문도 함께 제거된다.")
    void removeProduct_thenDeleteItsAgentReviewsAndQuestions() {
        // given: 상품 2개 중 하나만 제거한다.
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product target = createProduct("상품 A", null);
        target.startDiagnosis();
        target.recordAgentReview(AgentType.CHILDREN, AgentReviewStatus.COMPLETED, "완구에 해당합니다.");
        target.askQuestions(List.of(new QuestionContent("target_age", 1, "실제로 주로 판매하는 대상 연령은?", null)));
        Product remaining = createProduct("상품 B", null);
        remaining.startDiagnosis();
        remaining.recordAgentReview(AgentType.CHILDREN, AgentReviewStatus.SKIPPED, "어린이제품이 아닙니다.");
        remaining.askQuestions(List.of(new QuestionContent("target_age", 1, "실제로 주로 판매하는 대상 연령은?", null)));
        diagnoses.addProducts(List.of(target, remaining));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Diagnoses loaded = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow();
        loaded.removeProduct(loaded.getProducts().getFirst());
        flushAndClear();

        // then
        assertThat(countProducts()).isEqualTo(1);
        assertThat(countAgentReviews()).isEqualTo(1);
        assertThat(countQuestions()).isEqualTo(1);
    }

    private Diagnoses createDiagnosesWithReviewAndQuestion() {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.recordAgentReview(AgentType.INTAKE, AgentReviewStatus.COMPLETED, "상세페이지를 인식했습니다.");
        product.askQuestions(List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null)));
        diagnoses.addProducts(List.of(product));
        return diagnoses;
    }

    private Diagnoses createDiagnoses(UUID userId, ResultStatus resultStatus) {
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

    private long countAgentReviews() {
        return entityManager.createQuery("select count(r) from AgentReview r", Long.class).getSingleResult();
    }

    private long countQuestions() {
        return entityManager.createQuery("select count(q) from ProductQuestion q", Long.class).getSingleResult();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
