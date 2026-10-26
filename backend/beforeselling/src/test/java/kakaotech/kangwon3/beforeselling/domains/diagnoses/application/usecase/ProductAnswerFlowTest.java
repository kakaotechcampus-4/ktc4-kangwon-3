package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductAnswerRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductQuestionResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductQuestion;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
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
import static org.assertj.core.api.Assertions.tuple;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.timeout;

/**
 * 답변 제출부터 커밋 뒤 비동기 재진단 요청, 새 실행 식별자 저장까지 실제 DB와 트랜잭션으로 확인한다.
 * AI 서버만 목으로 둔다.
 */
@SpringBootTest
@ActiveProfiles("test")
class ProductAnswerFlowTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Autowired
    private ProductUseCase productUseCase;

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
    @DisplayName("답변을 제출하면 답변이 저장되고, 커밋 뒤 AI에 재진단을 요청해 새 실행 식별자를 저장한다.")
    void answerQuestions_thenSaveAnswersRequestResumeAndAssignNewRun() {
        // given
        Product product = saveAwaitingInputProduct();
        List<ProductQuestion> questions = product.getQuestions();
        given(aiDiagnosesClient.requestResume(any()))
                .willReturn(new AiResumeAccepted(product.getId().toString(), "run-2", "accepted"));

        // when
        productUseCase.answerQuestions(USER_ID, product.getId(), new ProductAnswerRequest(List.of(
                new ProductAnswerRequest.Answer(questions.get(0).getId(), "구매대행"),
                new ProductAnswerRequest.Answer(questions.get(1).getId(), "네"))));

        // then: 답변 저장과 상태 전이는 요청 안에서 끝난다.
        ProductResponse response = productUseCase.getProduct(USER_ID, product.getId());
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(response.questions())
                .extracting(ProductQuestionResponse::questionText, ProductQuestionResponse::answerText)
                .containsExactly(tuple("구매대행으로 파나요?", "구매대행"), tuple("내장 배터리로만 동작하나요?", "네"));

        // then: AI 요청과 새 실행 식별자 저장은 커밋 뒤 비동기로 일어난다.
        ArgumentCaptor<AiResumeRequest> captor = ArgumentCaptor.forClass(AiResumeRequest.class);
        then(aiDiagnosesClient).should(timeout(3000)).requestResume(captor.capture());
        assertThat(captor.getValue().runId()).isEqualTo("run-1");
        assertThat(captor.getValue().answers()).containsExactly(
                new AiResumeRequest.Answer("sales_type", "구매대행"),
                new AiResumeRequest.Answer("battery_only", "네"));

        await().atMost(Duration.ofSeconds(3)).untilAsserted(() ->
                assertThat(productRepository.findById(product.getId()).orElseThrow().getRunId()).isEqualTo("run-2"));
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
}
