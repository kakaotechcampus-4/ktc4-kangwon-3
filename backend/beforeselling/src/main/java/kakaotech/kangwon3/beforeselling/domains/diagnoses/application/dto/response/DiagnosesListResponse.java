package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import java.util.List;

public record DiagnosesListResponse(
        List<DiagnosesSummaryResponse> diagnoses,
        PageInfo pageInfo
) {

    public record PageInfo(
            int page,
            int size,
            long totalElements,
            int totalPages,
            boolean hasNext
    ) {
    }
}
