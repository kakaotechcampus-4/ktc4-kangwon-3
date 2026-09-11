package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesCreateCommand;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class DiagnosesMapper {

    public DiagnosesCreateCommand toCommand(Long userId, DiagnosesCreateRequest request) {
        return new DiagnosesCreateCommand(
                userId,
                request.productName(),
                request.productImageUrl(),
                request.sourceType(),
                request.sourceUrl(),
                request.sourceText(),
                request.imageUrls() == null ? List.of() : request.imageUrls()
        );
    }

    public DiagnosesDetailResponse toDetailResponse(Diagnoses diagnoses, List<DiagnosesImage> images) {
        List<String> imageUrls = images.stream()
                .map(DiagnosesImage::getImageUrl)
                .toList();

        return new DiagnosesDetailResponse(
                diagnoses.getId(),
                diagnoses.getProductName(),
                diagnoses.getProductImageUrl(),
                diagnoses.getSourceType(),
                diagnoses.getSourceUrl(),
                diagnoses.getSourceText(),
                imageUrls,
                diagnoses.getProcessingStatus(),
                diagnoses.getResultStatus(),
                diagnoses.getSummary(),
                diagnoses.getCreatedAt(),
                diagnoses.getUpdatedAt()
        );
    }

    public DiagnosesSummaryResponse toSummaryResponse(Diagnoses diagnoses) {
        return new DiagnosesSummaryResponse(
                diagnoses.getId(),
                diagnoses.getProductName(),
                diagnoses.getProductImageUrl(),
                diagnoses.getProcessingStatus(),
                diagnoses.getResultStatus(),
                diagnoses.getCreatedAt()
        );
    }

    public DiagnosesListResponse toListResponse(Page<Diagnoses> page) {
        List<DiagnosesSummaryResponse> diagnoses = page.getContent().stream()
                .map(this::toSummaryResponse)
                .toList();

        return new DiagnosesListResponse(diagnoses, toPageInfo(page));
    }

    private DiagnosesListResponse.PageInfo toPageInfo(Page<?> page) {
        return new DiagnosesListResponse.PageInfo(
                page.getNumber(),
                page.getSize(),
                page.getTotalElements(),
                page.getTotalPages(),
                page.hasNext()
        );
    }
}
