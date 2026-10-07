package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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
