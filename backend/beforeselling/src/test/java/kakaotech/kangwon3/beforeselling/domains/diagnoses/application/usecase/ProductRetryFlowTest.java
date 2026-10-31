package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductQuestionResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesRequestException;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.timeout;

/**
 * 실패한 상품 재시도부터 커밋 뒤 비동기 진단 요청, 새 실행 식별자 저장, 새 실행의 질문 저장까지 실제 DB와 트랜잭션으로 확인한다.
 * AI 서버만 목으로 둔다.
 */
@SpringBootTest
@ActiveProfiles("test")
class ProductRetryFlowTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductUseCase productUseCase;

    @Autowired
    private ProductService productService;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private ProductRepository productRepository;

    @MockitoBean
    private AiDiagnosesClient aiDiagnosesClient;

    @AfterEach
    void tearDown() {
        diagnosesRepository.deleteAll();
    }

    @Test
    @DisplayName("재시도하면 이전 실행의 질문·진행·실패 정보가 지워지고, 커밋 뒤 그 상품만 AI에 다시 요청해 새 실행 식별자를 저장한다.")
    void retryDiagnoses_thenResetAndRequestAndAssignNewRun() {
        // given
        Diagnoses diagnoses = saveFailedDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        givenAccepted(diagnoses, product);

        // when
        productUseCase.retryDiagnoses(USER_ID, product.getId());

        // then: 상태 초기화는 요청 안에서 끝난다.
        ProductResponse response = productUseCase.getProduct(USER_ID, product.getId());
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(response.failure()).isNull();
        assertThat(response.questions()).isEmpty();
        assertThat(response.progresses()).isEmpty();
        assertThat(productRepository.findById(product.getId()).orElseThrow().getRequestedAt())
                .isAfter(LocalDateTime.now().minusMinutes(1));

        // then: AI 요청과 새 실행 식별자 저장은 커밋 뒤 비동기로 일어난다.
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should(timeout(3000)).requestDiagnoses(captor.capture());
        assertThat(captor.getValue().diagnosisId()).isEqualTo(diagnoses.getId().toString());
        assertThat(captor.getValue().products())
                .extracting(AiDiagnosesRequest.Product::productId, AiDiagnosesRequest.Product::sourceUrl)
                .containsExactly(tuple(product.getId().toString(), SOURCE_URL));

        awaitRunId(product, "run-2");
    }

    @Test
    @DisplayName("재시도한 새 실행은 이전 실행과 같은 키의 1회차 질문을 다시 받을 수 있다.")
    void retryDiagnoses_thenAcceptFirstRoundQuestionsAgain() {
        // given
        Diagnoses diagnoses = saveFailedDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        givenAccepted(diagnoses, product);
        productUseCase.retryDiagnoses(USER_ID, product.getId());
        awaitRunId(product, "run-2");

        // when: 새 실행이 이전 실행과 같은 질문 키로 1회차 질문을 보낸다.
        productService.askQuestions(diagnoses.getId(), product.getId(), "run-2", 1,
                List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));

        // then
        ProductResponse response = productUseCase.getProduct(USER_ID, product.getId());
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(response.questions())
                .extracting(ProductQuestionResponse::questionRound, ProductQuestionResponse::answerText)
                .containsExactly(tuple(1, null));
    }

    @Test
    @DisplayName("재시도 요청을 AI가 이전 진단 진행 중으로 거절(409)하면 상품을 바로 재시도 가능한 실패로 끝낸다.")
    void retryDiagnoses_whenAiConflict_thenFailImmediately() {
        // given
        Diagnoses diagnoses = saveFailedDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        given(aiDiagnosesClient.requestDiagnoses(any()))
                .willThrow(AiDiagnosesRequestException.conflict(List.of(product.getId().toString()), null));

        // when
        productUseCase.retryDiagnoses(USER_ID, product.getId());

        // then
        await().atMost(Duration.ofSeconds(3)).untilAsserted(() -> {
            Product found = productRepository.findById(product.getId()).orElseThrow();
            assertThat(found.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
            assertThat(found.getErrorCode()).isEqualTo("BE_AI_REQUEST_CONFLICT");
            assertThat(found.getErrorRetryable()).isTrue();
        });
    }

    private void givenAccepted(Diagnoses diagnoses, Product product) {
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(new AiDiagnosesAccepted(
                diagnoses.getId().toString(),
                List.of(new AiDiagnosesAccepted.AcceptedProduct(product.getId().toString(), "run-2", "accepted"))));
    }

    private void awaitRunId(Product product, String runId) {
        await().atMost(Duration.ofSeconds(3)).untilAsserted(() ->
                assertThat(productRepository.findById(product.getId()).orElseThrow().getRunId()).isEqualTo(runId));
    }

    // 1회차 질문에 답하고 진행 상태를 받은 뒤 멈춘 진단으로 실패한 상품. 오래전에 요청한 것으로 둔다.
    private Diagnoses saveFailedDiagnoses() {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(Product.pending("보조배터리", null, SourceType.URL, SOURCE_URL, null)));
        diagnoses.startDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        product.assignRun("run-1");
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));
        product.getQuestions().forEach(question -> question.answer("구매대행"));
        product.resume();
        product.recordProgress("run-1", 1, PipelineStage.EXTRACTION, StageStatus.STARTED, null);
        product.fail(null, "BE_DIAGNOSES_TIMEOUT", "진단 결과를 받지 못해 진단을 종료했습니다.", true);
        ReflectionTestUtils.setField(product, "requestedAt", LocalDateTime.now().minusDays(1));
        diagnoses.refreshProcessingStatus();
        return diagnosesRepository.save(diagnoses);
    }
}
