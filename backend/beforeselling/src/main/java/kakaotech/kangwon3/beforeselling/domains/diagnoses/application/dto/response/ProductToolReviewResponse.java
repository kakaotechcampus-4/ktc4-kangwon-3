package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;

import java.util.List;
import java.util.UUID;

// 진단 결과의 분야별 카드
public record ProductToolReviewResponse(
        @Schema(example = "3c7a1e9d-2b4f-4a6c-8d0e-5f1b2c3d4e5a")
        UUID productToolReviewId,

        @Schema(example = "RADIO")
        ToolName toolName,

        @Schema(example = "COMPLETED")
        ToolReviewStatus status,

        @Schema(description = "분야 검토 결과 안내. 없으면 null", example = "2.4GHz 무선통신 기능이 있어 전파법 적합성평가 대상 여부를 확인했습니다.")
        String message,

        List<ProductFindingResponse> findings
) {
}
