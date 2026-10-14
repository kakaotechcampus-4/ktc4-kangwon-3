package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product_question",
        // 회차가 다르면 같은 키로 다시 물을 수 있다.
        uniqueConstraints = @UniqueConstraint(
                name = "uk_product_question_product_id_round_key",
                columnNames = {"product_id", "question_round", "question_key"}
        )
)
public class ProductQuestion extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_question_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    // AI가 보낸 질문 회차(1부터, 최대 2)
    @Column(name = "question_round", nullable = false, columnDefinition = "integer default 1")
    private int questionRound;

    @Column(name = "question_key", nullable = false, length = 50)
    private String questionKey;

    @Column(name = "question_order", nullable = false)
    private int questionOrder;

    @Column(name = "question_text", nullable = false, columnDefinition = "TEXT")
    private String questionText;

    @Column(name = "help_text", columnDefinition = "TEXT")
    private String helpText;

    @Column(name = "answer_text", columnDefinition = "TEXT")
    private String answerText;

    ProductQuestion(Product product, int questionRound, String questionKey, int questionOrder,
                    String questionText, String helpText) {
        this.product = product;
        this.questionRound = questionRound;
        this.questionKey = questionKey;
        this.questionOrder = questionOrder;
        this.questionText = questionText;
        this.helpText = helpText;
    }

    // 질문은 한 번만 받으므로 답변도 한 번만 저장한다.
    public void answer(String answerText) {
        if (isAnswered()) {
            throw new BaseException(CommonResponseCode.CONFLICT);
        }
        this.answerText = answerText;
    }

    public boolean isAnswered() {
        return answerText != null;
    }


}
