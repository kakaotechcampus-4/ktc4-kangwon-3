package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.global.common.PageInfo;

import java.util.List;

public record ProductListResponse(
        List<ProductSummaryResponse> products,
        PageInfo pageInfo
) {
}
