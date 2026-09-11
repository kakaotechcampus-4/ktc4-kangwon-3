package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import org.springframework.data.domain.Page;

import java.util.List;

public record DiagnosesListResponse(
        List<DiagnosesSummaryResponse> diagnoses,
        PageInfo page
) {

    public static DiagnosesListResponse from(Page<Diagnoses> page) {
        List<DiagnosesSummaryResponse> diagnoses = page.getContent().stream()
                .map(DiagnosesSummaryResponse::from)
                .toList();

        return new DiagnosesListResponse(diagnoses, PageInfo.from(page));
    }

    public record PageInfo(
            int number,
            int size,
            long totalElements,
            int totalPages,
            boolean hasNext
    ) {

        private static PageInfo from(Page<?> page) {
            return new PageInfo(
                    page.getNumber(),
                    page.getSize(),
                    page.getTotalElements(),
                    page.getTotalPages(),
                    page.hasNext()
            );
        }
    }
}