package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceException;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
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
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

// 결과 엔티티는 아직 변경 메서드가 없어(콜백 구현 때 추가) 같은 패키지에서 생성자로 직접 구성한다.
@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({JpaAuditingConfig.class, DatabaseEncryptionConverter.class})
@EnableConfigurationProperties(CryptoProperties.class)
class ProductResultMappingTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    @DisplayName("결과 카드·판단·법령 근거를 저장하면 상품을 다시 읽을 때 순서대로 함께 조회된다.")
    void save_thenPersistToolReviewsWithFindingsAndLegalSourcesInOrder() {
        // given: 판단과 법령 근거를 순서와 반대로 추가한다.
        Product product = createProduct();
        ReflectionTestUtils.setField(product, "assessmentStatus", AssessmentStatus.COMPLETED);
        ReflectionTestUtils.setField(product, "resultStatus", ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED);

        ProductToolReview children = new ProductToolReview(product, ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null);
        ProductFinding labeling = new ProductFinding(children, 1, "표시사항", Determination.POSSIBLY_REQUIRED,
                RiskLevel.MEDIUM, "사용연령 표시를 확인해야 합니다.", "상세페이지에 사용연령 표기가 없습니다.");
        ProductFinding certification = new ProductFinding(children, 0, "안전확인 대상 여부", Determination.REQUIRED,
                RiskLevel.HIGH, "안전확인이 필요합니다.", "권장연령 3-6세 기준으로 완구에 해당합니다.");
        certification.getLegalSources().add(new FindingLegalSource(certification, 1, "국가법령정보센터",
                "어린이제품 안전 특별법", "제17조", null, null, null));
        certification.getLegalSources().add(new FindingLegalSource(certification, 0, "국가법령정보센터",
                "어린이제품 안전 특별법 시행규칙", "별표 2", "완구: 14세 미만의 어린이가 놀이용으로 사용하는 제품",
                "https://www.law.go.kr", "2026-01-01"));
        children.getFindings().add(labeling);
        children.getFindings().add(certification);

        product.getToolReviews().add(children);
        product.getToolReviews().add(new ProductToolReview(product, ToolName.FOOD_DRUG, ToolReviewStatus.SKIPPED,
                "식품 접촉 성분이 감지되지 않아 검토하지 않았습니다."));
        UUID diagnosesId = save(product);
        flushAndClear();

        // when
        Product saved = findProduct(diagnosesId);

        // then
        assertThat(saved.getAssessmentStatus()).isEqualTo(AssessmentStatus.COMPLETED);
        assertThat(saved.getResultStatus()).isEqualTo(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED);
        assertThat(saved.getToolReviews())
                .extracting(ProductToolReview::getToolName, ProductToolReview::getStatus)
                .containsExactlyInAnyOrder(
                        tuple(ToolName.CHILDREN, ToolReviewStatus.COMPLETED),
                        tuple(ToolName.FOOD_DRUG, ToolReviewStatus.SKIPPED));

        ProductToolReview savedChildren = findToolReview(saved, ToolName.CHILDREN);
        assertThat(savedChildren.getFindings())
                .extracting(ProductFinding::getSubject, ProductFinding::getDetermination, ProductFinding::getRiskLevel)
                .containsExactly(
                        tuple("안전확인 대상 여부", Determination.REQUIRED, RiskLevel.HIGH),
                        tuple("표시사항", Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM));
        assertThat(savedChildren.getFindings().getFirst().getLegalSources())
                .extracting(FindingLegalSource::getLawName, FindingLegalSource::getArticle)
                .containsExactly(
                        tuple("어린이제품 안전 특별법 시행규칙", "별표 2"),
                        tuple("어린이제품 안전 특별법", "제17조"));

        assertThat(findToolReview(saved, ToolName.FOOD_DRUG).getFindings()).isEmpty();
    }

    @Test
    @DisplayName("필수 조치와 안내 문구는 받은 순서대로 저장된다.")
    void save_thenPersistRequiredActionsAndNoticesInOrder() {
        // given
        Product product = createProduct();
        product.getRequiredActions().addAll(List.of("안전확인(KC) 신고 후 판매", "공급사에 시험성적서 요청"));
        product.getNotices().addAll(List.of("상세페이지 이미지 일부를 읽지 못했습니다.", "전파 인증 여부는 확인하지 못했습니다."));
        UUID diagnosesId = save(product);
        flushAndClear();

        // when
        Product saved = findProduct(diagnosesId);

        // then
        assertThat(saved.getRequiredActions())
                .containsExactly("안전확인(KC) 신고 후 판매", "공급사에 시험성적서 요청");
        assertThat(saved.getNotices())
                .containsExactly("상세페이지 이미지 일부를 읽지 못했습니다.", "전파 인증 여부는 확인하지 못했습니다.");
    }

    @Test
    @DisplayName("결과를 받기 전인 상품은 결과 상태가 없고 결과 카드·조치·안내가 비어 있다.")
    void save_withoutResult_thenEmptyResult() {
        // given
        UUID diagnosesId = save(createProduct());
        flushAndClear();

        // when
        Product saved = findProduct(diagnosesId);

        // then
        assertThat(saved.getAssessmentStatus()).isNull();
        assertThat(saved.getToolReviews()).isEmpty();
        assertThat(saved.getRequiredActions()).isEmpty();
        assertThat(saved.getNotices()).isEmpty();
    }

    @Test
    @DisplayName("한 상품에 같은 분야 결과 카드를 두 번 저장하면 무결성 제약 위반이 발생한다.")
    void save_withDuplicateAgentType_thenThrowConstraintViolation() {
        // given
        Product product = createProduct();
        product.getToolReviews().add(new ProductToolReview(product, ToolName.CUSTOMS, ToolReviewStatus.COMPLETED, null));
        product.getToolReviews().add(new ProductToolReview(product, ToolName.CUSTOMS, ToolReviewStatus.INCOMPLETE, null));
        save(product);

        // when & then
        assertThatThrownBy(entityManager::flush).isInstanceOf(PersistenceException.class);
    }

    @Test
    @DisplayName("상품을 삭제하면 결과 카드·판단·법령 근거·조치·안내가 함께 삭제된다.")
    void delete_thenRemoveAllResultRows() {
        // given
        Product product = createProduct();
        ProductToolReview review = new ProductToolReview(product, ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null);
        ProductFinding finding = new ProductFinding(review, 0, "안전확인 대상 여부", Determination.REQUIRED,
                RiskLevel.HIGH, "안전확인이 필요합니다.", "완구에 해당합니다.");
        finding.getLegalSources().add(new FindingLegalSource(finding, 0, "국가법령정보센터",
                null, null, null, null, null));
        review.getFindings().add(finding);
        product.getToolReviews().add(review);
        product.getRequiredActions().add("안전확인(KC) 신고 후 판매");
        product.getNotices().add("전파 인증 여부는 확인하지 못했습니다.");
        UUID diagnosesId = save(product);
        flushAndClear();

        // when
        diagnosesRepository.delete(diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow());
        flushAndClear();

        // then
        assertThat(countRows("product_tool_review")).isZero();
        assertThat(countRows("product_finding")).isZero();
        assertThat(countRows("finding_legal_source")).isZero();
        assertThat(countRows("product_required_action")).isZero();
        assertThat(countRows("product_notice")).isZero();
    }

    private Product createProduct() {
        return Product.pending("대나무 헬리콥터", null, SourceType.URL, SOURCE_URL, null);
    }

    private UUID save(Product product) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(product));
        return diagnosesRepository.save(diagnoses).getId();
    }

    private Product findProduct(UUID diagnosesId) {
        return diagnosesRepository.findWithProductsById(diagnosesId).orElseThrow().getProducts().getFirst();
    }

    private ProductToolReview findToolReview(Product product, ToolName toolName) {
        return product.getToolReviews().stream()
                .filter(review -> review.getToolName() == toolName)
                .findFirst()
                .orElseThrow();
    }

    private long countRows(String table) {
        return ((Number) entityManager.createNativeQuery("select count(*) from " + table).getSingleResult()).longValue();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
