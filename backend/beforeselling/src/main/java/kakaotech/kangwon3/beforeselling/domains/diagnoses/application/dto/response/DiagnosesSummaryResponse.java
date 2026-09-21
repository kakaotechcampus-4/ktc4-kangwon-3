package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;

import java.time.LocalDateTime;
import java.util.UUID;

public record DiagnosesSummaryResponse(
        UUID diagnosesId,
        String productName,
        String productImageUrl,
        ProcessingStatus processingStatus,
        ResultStatus resultStatus,
        LocalDateTime createdAt
) {
}

