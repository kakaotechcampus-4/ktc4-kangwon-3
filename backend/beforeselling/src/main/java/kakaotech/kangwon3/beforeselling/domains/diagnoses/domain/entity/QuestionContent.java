package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

// AI가 보낸 질문 하나의 내용
public record QuestionContent(
        String questionKey,
        int questionOrder,
        String questionText,
        String helpText
) {
}
