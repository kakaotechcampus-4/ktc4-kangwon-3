package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

// 법령 개정 하나. products는 이 개정으로 다시 확인해야 하는 상품이다.
public record LawAmendmentResponse(
        UUID lawAmendmentId,
        String lawName,
        String revisionType,
        ToolName toolName,
        LocalDate enforceDate,
        List<RecheckProductResponse> products
) {

    public record RecheckProductResponse(
            UUID productId,
            String productName
    ) {
    }
}
