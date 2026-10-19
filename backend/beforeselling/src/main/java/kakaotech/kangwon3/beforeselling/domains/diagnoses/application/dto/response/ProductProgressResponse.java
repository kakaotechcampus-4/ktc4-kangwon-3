package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;

// 진단 진행 화면의 단계·Tool별 최신 상태
public record ProductProgressResponse(
        @Schema(example = "TOOL_EXECUTION")
        PipelineStage stage,

        @Schema(description = "stage가 TOOL_EXECUTION일 때만 값이 있음. 단계 자체의 진행이면 null", example = "RADIO")
        ToolName toolName,

        @Schema(example = "STARTED")
        StageStatus stageStatus
) {
}
