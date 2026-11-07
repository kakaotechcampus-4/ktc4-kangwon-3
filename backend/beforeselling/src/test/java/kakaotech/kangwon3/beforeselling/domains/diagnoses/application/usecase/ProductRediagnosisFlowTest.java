package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentProductRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentRepository;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.time.Duration;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.timeout;

/**
 * 진단을 마친 상품 재진단부터 이전 결과 삭제, 재확인 대상 해제, 커밋 뒤 AI 재요청까지 실제 DB와 트랜잭션으로 확인한다.
 * AI 서버만 목으로 둔다.
 */
@Tag("integration")
@SpringBootTest
@ActiveProfiles("test")
class ProductRediagnosisFlowTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductUseCase productUseCase;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private LawAmendmentRepository lawAmendmentRepository;

    @Autowired
    private LawAmendmentProductRepository lawAmendmentProductRepository;

    @MockitoBean
    private AiDiagnosesClient aiDiagnosesClient;

    @AfterEach
    void tearDown() {
        lawAmendmentProductRepository.deleteAll();
        lawAmendmentRepository.deleteAll();
        diagnosesRepository.deleteAll();
    }

    @Test
    @DisplayName("재진단하면 이전 결과와 재확인 연결이 지워지고, 커밋 뒤 그 상품만 AI에 다시 요청해 새 실행 식별자를 저장한다.")
    void rediagnoseProduct_thenClearResultAndRequestAgain() {
        // given
        Diagnoses diagnoses = saveCompletedDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        LawAmendment lawAmendment = lawAmendmentRepository.save(LawAmendment.builder()
                .lawName("어린이제품 안전 특별법 시행규칙")
                .documentId("012345")
                .toolName(ToolName.CHILDREN)
                .serialNumber("291321")
                .build());
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, product));
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(new AiDiagnosesAccepted(
                diagnoses.getId().toString(),
                List.of(new AiDiagnosesAccepted.AcceptedProduct(product.getId().toString(), "run-2", "accepted"))));

        // when
        productUseCase.rediagnoseProduct(USER_ID, product.getId());

        // then: 결과 삭제와 재확인 해제는 요청 안에서 끝난다.
        ProductResponse response = productUseCase.getProduct(USER_ID, product.getId());
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(response.resultStatus()).isNull();
        assertThat(response.toolReviews()).isEmpty();
        assertThat(lawAmendmentProductRepository.count()).isZero();
        assertThat(lawAmendmentRepository.count()).isOne();

        // then: AI 요청과 새 실행 식별자 저장은 커밋 뒤 비동기로 일어난다.
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should(timeout(3000)).requestDiagnoses(captor.capture());
        assertThat(captor.getValue().products())
                .extracting(AiDiagnosesRequest.Product::productId)
                .containsExactly(product.getId().toString());
        await().atMost(Duration.ofSeconds(3)).untilAsserted(() ->
                assertThat(productRepository.findById(product.getId()).orElseThrow().getRunId()).isEqualTo("run-2"));
    }

    // 법령 근거가 달린 분야별 결과까지 받은 완료 상품
    private Diagnoses saveCompletedDiagnoses() {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(Product.pending("대나무 헬리콥터", null, SourceType.URL, SOURCE_URL, null)));
        diagnoses.startDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        product.assignRun("run-1");
        product.complete(new AssessmentContent(AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED, "안전확인이 필요합니다.",
                List.of(new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                        List.of(new AssessmentContent.FindingContent("안전확인 대상 여부", Determination.REQUIRED,
                                RiskLevel.HIGH, "안전확인이 필요합니다.", "완구에 해당합니다.",
                                List.of(new AssessmentContent.LegalSourceContent("국가법령정보센터",
                                        "어린이제품 안전 특별법 시행규칙", "별표 2", null, null, null)))))),
                List.of("안전확인(KC) 신고 후 판매"), List.of("통관 시 확인")));
        diagnoses.refreshProcessingStatus();
        return diagnosesRepository.save(diagnoses);
    }
}
