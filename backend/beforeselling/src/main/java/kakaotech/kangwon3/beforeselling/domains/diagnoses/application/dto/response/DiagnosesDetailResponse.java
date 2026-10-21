package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

public record DiagnosesDetailResponse(
        UUID diagnosesId,
        ProcessingStatus processingStatus,

        @Schema(description = """
                다시 조회할 간격(ms). 대기·진행 중인 상품이 하나라도 있으면 값이 있고, 없으면 null(폴링 중단).
                진단서 상태가 AWAITING_INPUT이어도 다른 상품이 진행 중이면 값이 있음""", example = "3000")
        Long pollIntervalMs,
        List<ProductResponse> products,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}