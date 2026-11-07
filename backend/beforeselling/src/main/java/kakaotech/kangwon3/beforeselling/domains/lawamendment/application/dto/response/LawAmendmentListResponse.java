package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response;

import java.util.List;

public record LawAmendmentListResponse(
        List<LawAmendmentResponse> lawAmendments
) {
}
