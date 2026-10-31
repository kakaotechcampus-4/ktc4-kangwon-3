package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductAnswerRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler.PendingResumeRetryScheduler;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductQuestion;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.times;

/**
 * 답변 제출 뒤 재진단 요청이 AI에 전달되지 않았을 때, 재요청 대기 표시부터 스케줄러의 재전송·기한 실패까지
 * 실제 DB와 트랜잭션으로 확인한다. AI 서버만 목으로 둔다.
 */
@SpringBootTest
@ActiveProfiles("test")
class ProductResumeRetryFlowTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductUseCase productUseCase;

    @Autowired
    private PendingResumeRetryScheduler pendingResumeRetryScheduler;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockitoBean
    private AiDiagnosesClient aiDiagnosesClient;

    @AfterEach
    void tearDown() {
        diagnosesRepository.deleteAll();
    }

    @Test
    @DisplayName("재진단 요청을 AI가 받지 못하면 재요청 대기로 표시하고, 스케줄러가 저장된 답변을 다시 보내 새 실행 식별자를 저장한다.")
    void resume_whenNotReceived_thenResendSavedAnswersAndAssignNewRun() {
        // given
        Product product = saveAwaitingInputProduct();
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(serverError(HttpStatus.SERVICE_UNAVAILABLE))
                .willReturn(new AiResumeAccepted(product.getId().toString(), "run-2", "accepted"));
        answer(product);
        awaitResumePending(product);
        assertThat(findProduct(product).getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);

        // when
        pendingResumeRetryScheduler.retryPendingResumes();

        // then: 처음 요청과 같은 실행 ID·회차·답변을 다시 보낸다.
        ArgumentCaptor<AiResumeRequest> captor = ArgumentCaptor.forClass(AiResumeRequest.class);
        then(aiDiagnosesClient).should(times(2)).requestResume(captor.capture());
        assertThat(captor.getAllValues().get(1)).isEqualTo(captor.getAllValues().get(0));
        assertThat(captor.getAllValues().get(1).runId()).isEqualTo("run-1");
        assertThat(captor.getAllValues().get(1).answers()).containsExactly(
                new AiResumeRequest.Answer("sales_type", "구매대행"),
                new AiResumeRequest.Answer("battery_only", "네"));

        Product resumed = findProduct(product);
        assertThat(resumed.getRunId()).isEqualTo("run-2");
        assertThat(resumed.isResumePending()).isFalse();
        assertThat(resumed.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("처음 실패한 뒤 재요청 기한이 지나면 다시 보내지 않고 재시도 가능한 실패로 끝낸다.")
    void resume_whenPastDeadline_thenFailAsRetryableWithoutResend() {
        // given
        Product product = saveAwaitingInputProduct();
        given(aiDiagnosesClient.requestResume(any())).willThrow(serverError(HttpStatus.SERVICE_UNAVAILABLE));
        answer(product);
        awaitResumePending(product);
        jdbcTemplate.update("update product set resume_pending_since = ? where product_id = ?",
                LocalDateTime.now().minusMinutes(11), product.getId());

        // when
        pendingResumeRetryScheduler.retryPendingResumes();

        // then
        Product failed = findProduct(product);
        assertThat(failed.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(failed.getErrorCode()).isEqualTo("BE_AI_RESUME_UNAVAILABLE");
        assertThat(failed.getErrorRetryable()).isTrue();
        assertThat(failed.isResumePending()).isFalse();
        then(aiDiagnosesClient).should(times(1)).requestResume(any());
    }

    @Test
    @DisplayName("다시 보낸 재진단 요청이 충돌(409)하면 처음 요청이 접수됐을 수 있어 재시도 가능한 실패로 끝낸다.")
    void resume_whenResendConflict_thenFailAsRetryable() {
        // given
        Product product = saveAwaitingInputProduct();
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(serverError(HttpStatus.SERVICE_UNAVAILABLE))
                .willThrow(resumeConflict());
        answer(product);
        awaitResumePending(product);

        // when
        pendingResumeRetryScheduler.retryPendingResumes();

        // then
        Product failed = findProduct(product);
        assertThat(failed.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(failed.getErrorCode()).isEqualTo("AI_RESUME_CONFLICT");
        assertThat(failed.getErrorRetryable()).isTrue();
        assertThat(failed.isResumePending()).isFalse();
    }

    private void answer(Product product) {
        List<ProductQuestion> questions = product.getQuestions();
        productUseCase.answerQuestions(USER_ID, product.getId(), new ProductAnswerRequest(List.of(
                new ProductAnswerRequest.Answer(questions.get(0).getId(), "구매대행"),
                new ProductAnswerRequest.Answer(questions.get(1).getId(), "네"))));
    }

    // 답변 커밋 뒤 비동기 재진단 요청이 실패해 재요청 대기로 표시될 때까지 기다린다.
    private void awaitResumePending(Product product) {
        await().atMost(Duration.ofSeconds(3)).untilAsserted(() ->
                assertThat(findProduct(product).isResumePending()).isTrue());
    }

    private Product findProduct(Product product) {
        return productRepository.findById(product.getId()).orElseThrow();
    }

    private Product saveAwaitingInputProduct() {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(Product.pending("보조배터리", null, SourceType.URL, SOURCE_URL, null)));
        diagnoses.startDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        product.assignRun("run-1");
        product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null),
                new QuestionContent("battery_only", 2, "내장 배터리로만 동작하나요?", null)));
        diagnoses.refreshProcessingStatus();
        return diagnosesRepository.save(diagnoses).getProducts().getFirst();
    }

    private HttpServerErrorException serverError(HttpStatus status) {
        return HttpServerErrorException.create(status, status.getReasonPhrase(), HttpHeaders.EMPTY, new byte[0], null);
    }

    // RestClient가 던지는 것처럼 본문의 code를 읽을 수 있는 409 응답
    private HttpClientErrorException resumeConflict() {
        HttpClientErrorException exception = HttpClientErrorException.create(HttpStatus.CONFLICT, "Conflict",
                HttpHeaders.EMPTY, new byte[0], null);
        exception.setBodyConvertFunction(type -> new AiApiResponse<>("AI_RESUME_CONFLICT", "기다리는 질문과 다른 답변입니다.", null));
        return exception;
    }
}
