package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;

import java.time.LocalDateTime;

public record DiagnosesSummaryResponse(
        Long diagnosesId,
        String productName,
        String productImageUrl,
        ProcessingStatus processingStatus,
        ResultStatus resultStatus,
        LocalDateTime createdAt
) {

    public static DiagnosesSummaryResponse from(Diagnoses diagnoses) {
        return new DiagnosesSummaryResponse(
                diagnoses.getId(),
                diagnoses.getProductName(),
                diagnoses.getProductImageUrl(),
                diagnoses.getProcessingStatus(),
                diagnoses.getResultStatus(),
                diagnoses.getCreatedAt()
        );
    }
}