package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

class ProductTest {

    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Test
    @DisplayName("생성된 상품은 대기 상태다.")
    void pending_thenPending() {
        // when
        Product product = createProduct();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
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
    @DisplayName("답변 대기 중인 상품을 재진단하면 진행 중 상태가 된다.")
    void resume_whenAwaitingInput_thenInProgress() {
        // given
        Product product = createAwaitingInputProduct();

        // when
        product.resume();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("답변 대기 중이 아닌 상품을 재진단하면 CONFLICT 예외가 발생한다.")
    void resume_whenInProgress_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertConflict(product::resume);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
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
        Product product = createAwaitingInputProduct();

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
    @DisplayName("진행 중인 상품이 질문을 받으면 답변 없는 질문이 추가되고 답변 대기 상태가 된다.")
    void askQuestions_whenInProgress_thenAddQuestionsAndAwaitInput() {
        // given
        Product product = createInProgressProduct();

        // when
        product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null),
                new QuestionContent("target_age", 2, "실제로 주로 판매하는 대상 연령은?",
                        "상세페이지에 연령이 함께 적혀 있으면 확인이 필요합니다.")));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey,
                        ProductQuestion::getQuestionOrder, ProductQuestion::isAnswered)
                .containsExactly(tuple(1, "sales_type", 1, false), tuple(1, "target_age", 2, false));
        assertThat(product.getQuestions()).allSatisfy(question -> assertThat(question.getProduct()).isSameAs(product));
    }

    @Test
    @DisplayName("진행 중이 아닌 상품이 질문을 받으면 CONFLICT 예외가 발생하고 질문이 추가되지 않는다.")
    void askQuestions_whenPending_thenThrowConflict() {
        // given
        Product product = createProduct();

        // when & then
        assertConflict(() -> product.askQuestions(1,
                List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null))));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.getQuestions()).isEmpty();
    }

    @Test
    @DisplayName("답변 대기 중인 상품이 다시 질문을 받으면 CONFLICT 예외가 발생하고 질문이 늘지 않는다.")
    void askQuestions_whenAwaitingInput_thenThrowConflict() {
        // given
        Product product = createAwaitingInputProduct();

        // when & then
        assertConflict(() -> product.askQuestions(1,
                List.of(new QuestionContent("target_age", 1, "대상 연령은?", null))));
        assertThat(product.getQuestions()).hasSize(1);
    }

    @Test
    @DisplayName("답변 후 재진단 중인 상품은 다시 질문을 받을 수 있다.")
    void askQuestions_whenResumed_thenAddQuestionsAndAwaitInput() {
        // given: 질문 횟수(최대 2회)는 AI가 제한하므로 BE는 상태만 확인한다.
        Product product = createAwaitingInputProduct();
        product.resume();

        // when
        product.askQuestions(2, List.of(new QuestionContent("target_age", 1, "대상 연령은?", null)));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey)
                .containsExactly(tuple(1, "sales_type"), tuple(2, "target_age"));
    }

    @Test
    @DisplayName("빈 질문 목록을 받으면 BAD_REQUEST 예외가 발생하고 상태가 바뀌지 않는다.")
    void askQuestions_whenEmpty_thenThrowBadRequest() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.askQuestions(1, List.of()));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("같은 키의 질문이 함께 오면 BAD_REQUEST 예외가 발생하고 아무것도 저장되지 않는다.")
    void askQuestions_whenDuplicateKey_thenThrowBadRequest() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null),
                new QuestionContent("sales_type", 2, "사입해서 파나요?", null))));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getQuestions()).isEmpty();
    }

    private Product createProduct() {
        return Product.pending(PRODUCT_NAME, null, SourceType.URL, SOURCE_URL, null);
    }

    private Product createInProgressProduct() {
        Product product = createProduct();
        product.startDiagnosis();
        return product;
    }

    private Product createAwaitingInputProduct() {
        Product product = createInProgressProduct();
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));
        return product;
    }

    private void assertConflict(ThrowingCallable action) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
    }

    private void assertBadRequest(ThrowingCallable action) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.BAD_REQUEST);
    }
}
