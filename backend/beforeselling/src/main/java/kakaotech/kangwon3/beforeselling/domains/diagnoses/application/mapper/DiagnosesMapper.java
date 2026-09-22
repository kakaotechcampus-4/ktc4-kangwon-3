package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductCreateCommand;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DiagnosesMapper {

    private final S3UrlKeyCodec s3UrlKeyCodec;

    public ProductCreateCommand toCommand(Long userId, DiagnosesCreateRequest request) {
        return new ProductCreateCommand(
                userId,
                request.productName(),
                request.productImageKey(),
                request.sourceType(),
                request.sourceUrl(),
                request.sourceText(),
                request.imageKeys() == null ? List.of() : request.imageKeys()
        );
    }

    public DiagnosesCreateResponse toCreateResponse(Product product) {
        return new DiagnosesCreateResponse(product.getId());
    }

    public DiagnosesDetailResponse toDetailResponse(Product product) {
        List<String> imageUrls = product.getImages().stream()
                .map(ProductImage::getImageKey)
                .map(s3UrlKeyCodec::toUrl)
                .toList();

        return new DiagnosesDetailResponse(
                product.getId(),
                product.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(product.getProductImageKey()),
                product.getSourceType(),
                product.getSourceUrl(),
                product.getSourceText(),
                imageUrls,
                product.getProcessingStatus(),
                product.getResultStatus(),
                product.getSummary(),
                product.getCreatedAt(),
                product.getUpdatedAt()
        );
    }

    public DiagnosesSummaryResponse toSummaryResponse(Product product) {
        return new DiagnosesSummaryResponse(
                product.getId(),
                product.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(product.getProductImageKey()),
                product.getProcessingStatus(),
                product.getResultStatus(),
                product.getCreatedAt()
        );
    }

    public DiagnosesListResponse toListResponse(Page<Product> page) {
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
