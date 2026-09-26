package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.global.common.PageInfo;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class ProductMapper {

    private final S3UrlKeyCodec s3UrlKeyCodec;

    public ProductSummaryResponse toSummaryResponse(Product product) {
        return new ProductSummaryResponse(
                product.getId(),
                product.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(product.getProductImageKey()),
                product.getSourceType(),
                product.getProcessingStatus(),
                product.getResultStatus(),
                product.getCreatedAt()
        );
    }

    public ProductListResponse toListResponse(Page<Product> page) {
        List<ProductSummaryResponse> products = page.getContent().stream()
                .map(this::toSummaryResponse)
                .toList();

        return new ProductListResponse(products, PageInfo.from(page));
    }
}
