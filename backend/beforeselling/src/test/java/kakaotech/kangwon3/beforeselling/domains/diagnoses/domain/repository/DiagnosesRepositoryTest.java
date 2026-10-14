package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AgentType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductProgress;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductQuestion;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
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
import static org.assertj.core.api.Assertions.tuple;
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
    @DisplayName("상품의 질문은 상품과 함께 저장되고, 질문 순서대로 조회된다.")
    void save_thenPersistQuestionsInOrder() {
        // given: 질문을 순서와 반대로 추가한다.
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.askQuestions(1, List.of(
                new QuestionContent("target_age", 2, "실제로 주로 판매하는 대상 연령은?", null),
                new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null)));
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Product saved = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();

        // then
        assertThat(saved.getQuestions())
                .extracting(ProductQuestion::getQuestionKey)
                .containsExactly("sales_type", "target_age");
    }

    @Test
    @DisplayName("2회차에 1회차와 같은 키로 질문해도 저장되고, 질문은 회차·순서대로 조회된다.")
    void save_whenSameKeyInNextRound_thenPersistBothInRoundOrder() {
        // given: 1회차 답이 불분명해 2회차에 같은 항목을 다시 묻는 경우
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null),
                new QuestionContent("target_age", 2, "실제로 주로 판매하는 대상 연령은?", null)));
        product.resume();
        product.askQuestions(2, List.of(new QuestionContent("sales_type", 1, "주로 어느 쪽으로 파나요?", null)));
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Product saved = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();

        // then
        assertThat(saved.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey)
                .containsExactly(tuple(1, "sales_type"), tuple(1, "target_age"), tuple(2, "sales_type"));
    }

    @Test
    @DisplayName("상품의 진행 상태는 툴이 없는 단계와 툴별 단계가 함께 저장되고 조회된다.")
    void save_thenPersistProgresses() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.recordProgress("run-1", 1, PipelineStage.EXTRACTION, StageStatus.COMPLETED, null);
        product.recordProgress("run-1", 2, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, AgentType.CUSTOMS);
        product.recordProgress("run-1", 3, PipelineStage.TOOL_EXECUTION, StageStatus.SKIPPED, AgentType.RADIO);
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Product saved = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();

        // then
        assertThat(saved.getProgresses())
                .extracting(ProductProgress::getRunId, ProductProgress::getSequence, ProductProgress::getStage,
                        ProductProgress::getStageStatus, ProductProgress::getToolName)
                .containsExactlyInAnyOrder(
                        tuple("run-1", 1, PipelineStage.EXTRACTION, StageStatus.COMPLETED, null),
                        tuple("run-1", 2, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, AgentType.CUSTOMS),
                        tuple("run-1", 3, PipelineStage.TOOL_EXECUTION, StageStatus.SKIPPED, AgentType.RADIO));
    }

    @Test
    @DisplayName("실패한 상품의 실패 단계·오류 코드·메시지·재시도 여부가 저장되고 조회된다.")
    void save_whenFailed_thenPersistFailureInfo() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.fail(PipelineStage.TOOL_EXECUTION, "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", true);
        diagnoses.addProducts(List.of(product));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Product saved = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();

        // then
        assertThat(saved.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(saved)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsExactly(PipelineStage.TOOL_EXECUTION, "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", true);
    }

    @Test
    @DisplayName("진단서를 삭제하면 상품의 질문과 진행 상태도 함께 제거되고 다른 진단서의 것은 남는다.")
    void delete_thenDeleteOnlyItsQuestionsAndProgresses() {
        // given
        UUID targetId = diagnosesRepository.save(createDiagnosesWithQuestion()).getId();
        UUID otherId = diagnosesRepository.save(createDiagnosesWithQuestion()).getId();
        flushAndClear();

        // when
        diagnosesRepository.delete(diagnosesRepository.findById(targetId).orElseThrow());
        flushAndClear();

        // then
        assertThat(countQuestions()).isEqualTo(1);
        assertThat(countProgresses()).isEqualTo(1);
        assertThat(diagnosesRepository.findById(otherId)).isPresent();
    }

    @Test
    @DisplayName("진단서에서 상품을 제거하면 그 상품의 질문도 함께 제거된다.")
    void removeProduct_thenDeleteItsQuestions() {
        // given: 상품 2개 중 하나만 제거한다.
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product target = createProduct("상품 A", null);
        target.startDiagnosis();
        target.askQuestions(1, List.of(new QuestionContent("target_age", 1, "실제로 주로 판매하는 대상 연령은?", null)));
        Product remaining = createProduct("상품 B", null);
        remaining.startDiagnosis();
        remaining.askQuestions(1, List.of(new QuestionContent("target_age", 1, "실제로 주로 판매하는 대상 연령은?", null)));
        diagnoses.addProducts(List.of(target, remaining));
        UUID diagnosesId = diagnosesRepository.save(diagnoses).getId();
        flushAndClear();

        // when
        Diagnoses loaded = diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow();
        loaded.removeProduct(loaded.getProducts().getFirst());
        flushAndClear();

        // then
        assertThat(countProducts()).isEqualTo(1);
        assertThat(countQuestions()).isEqualTo(1);
    }

    private Diagnoses createDiagnosesWithQuestion() {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = createProduct("대나무 헬리콥터", null);
        product.startDiagnosis();
        product.recordProgress("run-1", 1, PipelineStage.EXTRACTION, StageStatus.COMPLETED, null);
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null)));
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

    private long countProgresses() {
        return entityManager.createQuery("select count(p) from ProductProgress p", Long.class).getSingleResult();
    }

    private long countQuestions() {
        return entityManager.createQuery("select count(q) from ProductQuestion q", Long.class).getSingleResult();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
