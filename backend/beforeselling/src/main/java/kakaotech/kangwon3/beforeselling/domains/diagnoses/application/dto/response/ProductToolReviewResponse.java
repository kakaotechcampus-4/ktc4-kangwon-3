package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;

import java.util.List;
import java.util.UUID;

// 진단 결과의 분야별 카드
public record ProductToolReviewResponse(
        UUID productToolReviewId,
        ToolName toolName,
        ToolReviewStatus status,
        String message,
        List<ProductFindingResponse> findings
) {
}
