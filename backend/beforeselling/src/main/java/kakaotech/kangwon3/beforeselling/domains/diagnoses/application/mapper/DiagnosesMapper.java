package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductCreateCommand;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DiagnosesMapper {

    private final S3UrlKeyCodec s3UrlKeyCodec;

    public List<ProductCreateCommand> toCommands(DiagnosesCreateRequest request) {
        return request.products().stream()
                .map(this::toCommand)
                .toList();
    }

    private ProductCreateCommand toCommand(ProductCreateRequest request) {
        return new ProductCreateCommand(
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
        List<ProductResponse> products = diagnoses.getProducts().stream()
                .map(this::toProductResponse)
                .toList();

        return new DiagnosesDetailResponse(
                diagnoses.getId(),
                diagnoses.getProcessingStatus(),
                products,
                diagnoses.getCreatedAt(),
                diagnoses.getUpdatedAt()
        );
    }

    private ProductResponse toProductResponse(Product product) {
        List<String> imageUrls = product.getImages().stream()
                .map(ProductImage::getImageKey)
                .map(s3UrlKeyCodec::toUrl)
                .toList();

        return new ProductResponse(
                product.getId(),
                product.getSortOrder(),
                product.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(product.getProductImageKey()),
                product.getSourceType(),
                product.getSourceUrl(),
                product.getSourceText(),
                imageUrls,
                product.getProcessingStatus(),
                product.getResultStatus(),
                product.getSummary()
        );
    }
}
