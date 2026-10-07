package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

class ProductTest {

    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Test
    @DisplayName("생성된 상품은 대기 상태이고 진단 회차는 0이다.")
    void pending_thenPendingWithRoundZero() {
        // when
        Product product = createProduct();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.getDiagnosisRound()).isZero();
    }

    @Test
    @DisplayName("대기 중인 상품의 진단을 시작하면 진행 중 상태가 된다.")
    void startDiagnosis_whenPending_thenInProgress() {
        // given
        Product product = createProduct();

        // when
        product.startDiagnosis();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이미 진단이 시작된 상품의 진단을 다시 시작하면 CONFLICT 예외가 발생한다.")
    void startDiagnosis_whenInProgress_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertConflict(product::startDiagnosis);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("진행 중인 상품이 질문을 받으면 답변 대기 상태가 된다.")
    void awaitInput_whenInProgress_thenAwaitingInput() {
        // given
        Product product = createInProgressProduct();

        // when
        product.awaitInput();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
    }

    @Test
    @DisplayName("진행 중이 아닌 상품이 질문을 받으면 CONFLICT 예외가 발생한다.")
    void awaitInput_whenPending_thenThrowConflict() {
        // given
        Product product = createProduct();

        // when & then
        assertConflict(product::awaitInput);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
    }

    @Test
    @DisplayName("답변 후 재진단(회차 1) 중인 상품이 다시 질문을 받으면 CONFLICT 예외가 발생한다.")
    void awaitInput_whenRoundExceeded_thenThrowConflict() {
        // given: 질문은 첫 진단(회차 0)에서만 받는다.
        Product product = createInProgressProduct();
        product.awaitInput();
        product.resume();

        // when & then
        assertConflict(product::awaitInput);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("답변 대기 중인 상품을 재진단하면 진행 중 상태가 되고 회차가 1 증가한다.")
    void resume_whenAwaitingInput_thenInProgressAndNextRound() {
        // given
        Product product = createInProgressProduct();
        product.awaitInput();

        // when
        product.resume();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getDiagnosisRound()).isEqualTo(1);
    }

    @Test
    @DisplayName("답변 대기 중이 아닌 상품을 재진단하면 CONFLICT 예외가 발생하고 회차는 그대로다.")
    void resume_whenInProgress_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertConflict(product::resume);
        assertThat(product.getDiagnosisRound()).isZero();
    }

    @Test
    @DisplayName("진행 중인 상품을 실패 처리하면 실패 상태가 된다.")
    void fail_whenInProgress_thenFailed() {
        // given
        Product product = createInProgressProduct();

        // when
        product.fail();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("답변 대기 중인 상품은 실패 처리할 수 없다.")
    void fail_whenAwaitingInput_thenThrowConflict() {
        // given: 답변 대기는 사용자를 기다리는 정상 상태다.
        Product product = createInProgressProduct();
        product.awaitInput();

        // when & then
        assertConflict(product::fail);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
    }

    @Test
    @DisplayName("이미 실패한 상품을 다시 실패 처리하면 CONFLICT 예외가 발생한다.")
    void fail_whenFailed_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();
        product.fail();

        // when & then
        assertConflict(product::fail);
    }

    @Test
    @DisplayName("처음 받은 에이전트 카드는 새로 추가된다.")
    void recordAgentReview_whenNew_thenAdd() {
        // given
        Product product = createInProgressProduct();

        // when
        product.recordAgentReview(AgentType.CUSTOMS, AgentReviewStatus.COMPLETED, "세관장확인 요건이 없습니다.");

        // then
        assertThat(product.getAgentReviews())
                .extracting(AgentReview::getAgentType, AgentReview::getStatus, AgentReview::getDescription)
                .containsExactly(tuple(AgentType.CUSTOMS, AgentReviewStatus.COMPLETED, "세관장확인 요건이 없습니다."));
    }

    @Test
    @DisplayName("같은 에이전트의 카드를 다시 받으면 새로 추가하지 않고 덮어쓴다.")
    void recordAgentReview_whenSameAgentType_thenOverwrite() {
        // given: 콜백이 중복으로 오거나 재진단에서 같은 카드가 다시 온 경우
        Product product = createInProgressProduct();
        product.recordAgentReview(AgentType.FOOD_DRUG, AgentReviewStatus.SKIPPED, "식품 접촉 항목이 없습니다.");

        // when
        product.recordAgentReview(AgentType.FOOD_DRUG, AgentReviewStatus.COMPLETED, "식품용 기구에 해당합니다.");

        // then
        assertThat(product.getAgentReviews())
                .extracting(AgentReview::getAgentType, AgentReview::getStatus, AgentReview::getDescription)
                .containsExactly(tuple(AgentType.FOOD_DRUG, AgentReviewStatus.COMPLETED, "식품용 기구에 해당합니다."));
    }

    @Test
    @DisplayName("서로 다른 에이전트의 카드는 각각 추가된다.")
    void recordAgentReview_whenDifferentAgentType_thenAddEach() {
        // given
        Product product = createInProgressProduct();

        // when
        product.recordAgentReview(AgentType.INTAKE, AgentReviewStatus.COMPLETED, "상세페이지를 인식했습니다.");
        product.recordAgentReview(AgentType.RADIO, AgentReviewStatus.SKIPPED, "무선 기능이 없습니다.");

        // then
        assertThat(product.getAgentReviews())
                .extracting(AgentReview::getAgentType)
                .containsExactly(AgentType.INTAKE, AgentType.RADIO);
    }

    @Test
    @DisplayName("질문을 추가하면 답변이 없는 상태로 상품에 연결된다.")
    void addQuestion_thenAddUnansweredQuestion() {
        // given
        Product product = createInProgressProduct();

        // when
        product.addQuestion("target_age", 1, "실제로 주로 판매하는 대상 연령은?", "상세페이지에 연령이 함께 적혀 있으면 확인이 필요합니다.");

        // then
        assertThat(product.getQuestions()).singleElement().satisfies(question -> {
            assertThat(question.getProduct()).isSameAs(product);
            assertThat(question.getQuestionKey()).isEqualTo("target_age");
            assertThat(question.getQuestionOrder()).isEqualTo(1);
            assertThat(question.isAnswered()).isFalse();
        });
    }

    private Product createProduct() {
        return Product.pending(PRODUCT_NAME, null, SourceType.URL, SOURCE_URL, null);
    }

    private Product createInProgressProduct() {
        Product product = createProduct();
        product.startDiagnosis();
        return product;
    }

    private void assertConflict(ThrowingCallable action) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
    }
}
