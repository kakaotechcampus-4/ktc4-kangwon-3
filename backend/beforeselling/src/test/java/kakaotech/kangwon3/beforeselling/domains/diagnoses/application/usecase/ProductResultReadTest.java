package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductProgressResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductQuestionResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductToolReviewResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

/**
 * open-in-view=false 라 DTO 매핑은 서비스 트랜잭션이 끝난 뒤에 일어난다.
 * 테스트 메서드에 트랜잭션을 걸지 않고 실제 조회 흐름(UseCase)을 그대로 실행해,
 * 지연 로딩되는 진단 결과가 매핑 전에 모두 읽혔는지 검증한다.
 */
@SpringBootTest
@ActiveProfiles("test")
class ProductResultReadTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductUseCase productUseCase;

    @Autowired
    private DiagnosesUseCase diagnosesUseCase;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @AfterEach
    void tearDown() {
        diagnosesRepository.deleteAll();
    }

    @Test
    @DisplayName("진단이 완료된 상품을 단건 조회하면 분야별 카드와 판단 항목, 법령 근거까지 함께 응답한다.")
    void getProduct_withCompletedAssessment_thenIncludeAssessmentDetails() {
        // given
        Diagnoses diagnoses = saveDiagnoses("대나무 헬리콥터");
        UUID productId = diagnoses.getProducts().getFirst().getId();

        // when
        ProductResponse response = productUseCase.getProduct(USER_ID, productId);

        // then
        assertAssessmentDetails(response);
    }

    @Test
    @DisplayName("진단서를 조회하면 진단이 완료된 모든 상품의 분야별 카드와 판단 항목, 법령 근거까지 함께 응답한다.")
    void getDiagnoses_withCompletedAssessments_thenIncludeAssessmentDetailsOfAllProducts() {
        // given
        Diagnoses diagnoses = saveDiagnoses("대나무 헬리콥터", "블루투스 스피커");

        // when
        DiagnosesDetailResponse response = diagnosesUseCase.getDiagnoses(USER_ID, diagnoses.getId());

        // then
        assertThat(response.products()).hasSize(2);
        response.products().forEach(this::assertAssessmentDetails);
    }

    @Test
    @DisplayName("진단 중인 진단서를 조회하면 상품별 진행 상태·질문·실패 정보와 폴링 간격까지 함께 응답한다.")
    void getDiagnoses_withProcessingProducts_thenIncludeProgressQuestionsFailureAndPollInterval() {
        // given: 진행 중 / 답변 대기 / 실패 상품
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(
                Product.pending("진행 중 상품", null, SourceType.URL, SOURCE_URL, null),
                Product.pending("답변 대기 상품", null, SourceType.URL, SOURCE_URL, null),
                Product.pending("실패 상품", null, SourceType.URL, SOURCE_URL, null)));
        diagnoses.startDiagnoses();
        diagnoses.getProducts().forEach(product -> product.assignRun("run-1"));
        List<Product> products = diagnoses.getProducts();
        products.get(0).recordProgress("run-1", 1, PipelineStage.EXTRACTION, StageStatus.COMPLETED, null);
        products.get(0).recordProgress("run-1", 2, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.RADIO);
        products.get(1).askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));
        products.get(2).fail(PipelineStage.TOOL_EXECUTION, "AI_TIMEOUT", "진단 시간이 초과되었습니다.", true);
        diagnoses.refreshProcessingStatus();
        diagnosesRepository.save(diagnoses);

        // when
        DiagnosesDetailResponse response = diagnosesUseCase.getDiagnoses(USER_ID, diagnoses.getId());

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(response.pollIntervalMs()).isEqualTo(3000L);

        ProductResponse inProgress = response.products().get(0);
        assertThat(inProgress.progresses())
                .extracting(ProductProgressResponse::stage, ProductProgressResponse::toolName)
                .containsExactly(tuple(PipelineStage.EXTRACTION, null), tuple(PipelineStage.TOOL_EXECUTION, ToolName.RADIO));

        ProductResponse awaitingInput = response.products().get(1);
        assertThat(awaitingInput.questions())
                .extracting(ProductQuestionResponse::questionText)
                .containsExactly("구매대행으로 파나요?");
        assertThat(awaitingInput.questions().getFirst().questionId()).isNotNull();

        ProductResponse failed = response.products().get(2);
        assertThat(failed.failure().errorCode()).isEqualTo("AI_TIMEOUT");
        assertThat(failed.failure().retryable()).isTrue();
    }

    private void assertAssessmentDetails(ProductResponse response) {
        assertThat(response.assessmentStatus()).isEqualTo(AssessmentStatus.COMPLETED);
        assertThat(response.requiredActions()).containsExactly("안전확인 신고");
        assertThat(response.notices()).containsExactly("구매대행으로 판매하면 결론이 달라질 수 있습니다.");
        assertThat(response.toolReviews())
                .extracting(ProductToolReviewResponse::toolName)
                .containsExactly(ToolName.CUSTOMS, ToolName.CHILDREN);

        ProductToolReviewResponse children = response.toolReviews().get(1);
        assertThat(children.findings()).hasSize(1);
        assertThat(children.findings().getFirst().legalSources()).hasSize(1);
    }

    private Diagnoses saveDiagnoses(String... productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(productNames).stream()
                .map(this::completedProduct)
                .toList());
        diagnoses.refreshProcessingStatus();
        return diagnosesRepository.save(diagnoses);
    }

    private Product completedProduct(String productName) {
        Product product = Product.pending(productName, null, SourceType.URL, SOURCE_URL, null);
        product.startDiagnoses();
        product.complete(new AssessmentContent(
                AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                List.of(
                        new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                                List.of(new AssessmentContent.FindingContent("안전확인 대상 여부",
                                        Determination.REQUIRED, RiskLevel.HIGH, "안전확인이 필요합니다.",
                                        "권장연령 3-6세 기준으로 완구에 해당합니다.",
                                        List.of(new AssessmentContent.LegalSourceContent("국가법령정보센터",
                                                "어린이제품 안전 특별법 시행규칙", "별표 2", null, null, null))))),
                        new AssessmentContent.ToolReviewContent(ToolName.CUSTOMS, ToolReviewStatus.SKIPPED,
                                "세관장확인 대상이 아닙니다.", List.of())),
                List.of("안전확인 신고"),
                List.of("구매대행으로 판매하면 결론이 달라질 수 있습니다.")));
        return product;
    }
}
