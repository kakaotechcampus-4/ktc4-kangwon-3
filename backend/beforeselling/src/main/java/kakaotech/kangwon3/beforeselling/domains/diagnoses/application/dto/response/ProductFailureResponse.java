package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;

// 진단 실패 정보
public record ProductFailureResponse(
        @Schema(description = "실패한 단계. 진단 시작 전 실패나 결과를 받지 못해 종료한 경우 null", example = "TOOL_EXECUTION")
        PipelineStage failedStage,

        @Schema(example = "AI_TIMEOUT")
        String errorCode,

        @Schema(example = "진단 시간이 초과되었습니다.")
        String errorMessage,

        @Schema(description = "다시 진단하면 성공할 수 있는지. 알 수 없으면 null", example = "true")
        Boolean retryable
) {
}
