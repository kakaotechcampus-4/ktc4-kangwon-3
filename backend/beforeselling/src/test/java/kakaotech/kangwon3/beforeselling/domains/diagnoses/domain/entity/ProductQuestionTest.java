package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ProductQuestionTest {

    @Test
    @DisplayName("답변하면 답변 내용이 저장되고 답변한 질문이 된다.")
    void answer_thenSaveAnswer() {
        // given
        ProductQuestion question = createQuestion();

        // when
        question.answer("재고를 미리 들여와서 팔아요.");

        // then
        assertThat(question.isAnswered()).isTrue();
        assertThat(question.getAnswerText()).isEqualTo("재고를 미리 들여와서 팔아요.");
    }

    @Test
    @DisplayName("이미 답변한 질문에 다시 답변하면 CONFLICT 예외가 발생하고 처음 답변이 유지된다.")
    void answer_whenAlreadyAnswered_thenThrowConflict() {
        // given
        ProductQuestion question = createQuestion();
        question.answer("재고를 미리 들여와서 팔아요.");

        // when & then
        assertThatThrownBy(() -> question.answer("구매대행으로 팔아요."))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
        assertThat(question.getAnswerText()).isEqualTo("재고를 미리 들여와서 팔아요.");
    }

    private ProductQuestion createQuestion() {
        Product product = Product.pending("대나무 헬리콥터", null, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null);
        product.startDiagnosis();
        product.askQuestions(List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null)));
        return product.getQuestions().getFirst();
    }
}
