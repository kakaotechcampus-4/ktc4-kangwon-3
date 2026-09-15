package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesCreateCommand;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DiagnosesMapper {

    private final S3UrlKeyCodec s3UrlKeyCodec;

    public DiagnosesCreateCommand toCommand(Long userId, DiagnosesCreateRequest request) {
        return new DiagnosesCreateCommand(
                userId,
                request.productName(),
                request.productImageKey(),
                request.sourceType(),
                request.sourceUrl(),
                request.sourceText(),
                request.imageKeys() == null ? List.of() : request.imageKeys()
        );
    }

    public DiagnosesCreateResponse toCreateResponse(Diagnoses diagnoses) {
        return new DiagnosesCreateResponse(diagnoses.getId());
    }

    public DiagnosesDetailResponse toDetailResponse(Diagnoses diagnoses) {
        List<String> imageUrls = diagnoses.getImages().stream()
                .map(DiagnosesImage::getImageKey)
                .map(s3UrlKeyCodec::toUrl)
                .toList();

        return new DiagnosesDetailResponse(
                diagnoses.getId(),
                diagnoses.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(diagnoses.getProductImageKey()),
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
                s3UrlKeyCodec.toUrlOrNull(diagnoses.getProductImageKey()),
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
