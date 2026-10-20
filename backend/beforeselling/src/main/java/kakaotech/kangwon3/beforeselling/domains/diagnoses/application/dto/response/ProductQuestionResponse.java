package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

// 진단 중 사용자에게 묻는 질문 하나
public record ProductQuestionResponse(
        @Schema(example = "5d2e8f1a-7c3b-4e9d-a6f0-1b2c3d4e5f6a")
        UUID questionId,

        @Schema(description = "질문 회차. 답변 후 재진단에서 다시 물으면 2", example = "1")
        int questionRound,

        @Schema(description = "회차 안에서의 표시 순서", example = "1")
        int questionOrder,

        @Schema(example = "구매대행으로 판매하시나요, 직접 사입해서 판매하시나요?")
        String questionText,

        @Schema(description = "질문 보조 설명. 없으면 null", example = "판매 형태에 따라 필요한 인증이 달라집니다.")
        String helpText,

        @Schema(description = "답변하기 전에는 null", example = "구매대행")
        String answerText
) {
}
