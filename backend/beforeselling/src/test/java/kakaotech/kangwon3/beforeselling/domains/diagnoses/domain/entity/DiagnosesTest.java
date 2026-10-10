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
    void startDiagnosis_thenAllProductsAndDiagnosesInProgress() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));

        // when
        diagnoses.startDiagnosis();

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsOnly(ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이미 진단을 시작한 진단서의 진단을 다시 시작하면 CONFLICT 예외가 발생한다.")
    void startDiagnosis_whenAlreadyStarted_thenThrowConflict() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        diagnoses.startDiagnosis();

        // when & then
        assertThatThrownBy(diagnoses::startDiagnosis)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
    }

    private Diagnoses createDiagnoses(List<String> productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(productNames.stream()
                .map(name -> Product.pending(name, null, SourceType.URL, SOURCE_URL, null))
                .toList());
        return diagnoses;
    }
}
