package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DiagnosesTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Test
    @DisplayName("진단을 시작하면 모든 상품과 진단서가 진행 중 상태가 된다.")
    void startDiagnoses_thenAllProductsAndDiagnosesInProgress() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));

        // when
        diagnoses.startDiagnoses();

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsOnly(ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이미 진단을 시작한 진단서의 진단을 다시 시작하면 CONFLICT 예외가 발생한다.")
    void startDiagnoses_whenAlreadyStarted_thenThrowConflict() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        diagnoses.startDiagnoses();

        // when & then
        assertThatThrownBy(diagnoses::startDiagnoses)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
    }

    @Test
    @DisplayName("대기 중인 상품이 있으면 진단 중인 상품이 있는 것으로 본다.")
    void hasProcessingProduct_whenPending_thenTrue() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));

        // when & then
        assertThat(diagnoses.hasProcessingProduct()).isTrue();
    }

    @Test
    @DisplayName("진단서가 답변 대기여도 진행 중인 상품이 남아 있으면 진단 중인 상품이 있는 것으로 본다.")
    void hasProcessingProduct_whenAwaitingInputWithInProgress_thenTrue() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        diagnoses.startDiagnoses();
        diagnoses.getProducts().getFirst().askQuestions(1, List.of(question()));
        diagnoses.refreshProcessingStatus();

        // when & then
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(diagnoses.hasProcessingProduct()).isTrue();
    }

    @Test
    @DisplayName("답변 대기·완료·실패 상품만 남으면 진단 중인 상품이 없는 것으로 본다.")
    void hasProcessingProduct_whenOnlyAwaitingInputOrFinished_thenFalse() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B", "상품 C"));
        diagnoses.startDiagnoses();
        List<Product> products = diagnoses.getProducts();
        products.get(0).askQuestions(1, List.of(question()));
        products.get(1).complete(new AssessmentContent(AssessmentStatus.COMPLETED,
                ResultStatus.PURCHASING_AGENT_ALLOWED, "구매대행으로 판매할 수 있습니다.", List.of(), List.of(), List.of()));
        products.get(2).fail(null, "AI_TIMEOUT", "시간이 초과되었습니다.", true);

        // when & then
        assertThat(diagnoses.hasProcessingProduct()).isFalse();
    }

    private QuestionContent question() {
        return new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null);
    }

    private Diagnoses createDiagnoses(List<String> productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(productNames.stream()
                .map(name -> Product.pending(name, null, SourceType.URL, SOURCE_URL, null))
                .toList());
        return diagnoses;
    }
}
