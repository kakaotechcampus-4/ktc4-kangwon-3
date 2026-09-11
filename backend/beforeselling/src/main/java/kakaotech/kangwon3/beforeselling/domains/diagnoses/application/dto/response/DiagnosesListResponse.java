package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import java.util.List;

public record DiagnosesListResponse(
        List<DiagnosesSummaryResponse> diagnoses,
        PageInfo page
) {

    public record PageInfo(
            int number,
            int size,
            long totalElements,
            int totalPages,
            boolean hasNext
    ) {
    }
}
