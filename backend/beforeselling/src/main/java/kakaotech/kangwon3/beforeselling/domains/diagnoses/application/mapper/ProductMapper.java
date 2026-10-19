package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.FindingLegalSourceResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductFindingResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductToolReviewResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.FindingLegalSource;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductFinding;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductToolReview;
import kakaotech.kangwon3.beforeselling.global.common.PageInfo;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Component;

import java.util.Comparator;
import java.util.List;

@Component
@RequiredArgsConstructor
public class ProductMapper {

    private final S3UrlKeyCodec s3UrlKeyCodec;

    public ProductSummaryResponse toSummaryResponse(Product product) {
        return new ProductSummaryResponse(
                product.getId(),
                product.getDiagnoses().getId(),
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

    public ProductResponse toResponse(Product product) {
        List<String> imageUrls = product.getImages().stream()
                .map(ProductImage::getImageKey)
                .map(s3UrlKeyCodec::toUrl)
                .toList();

        return new ProductResponse(
                product.getId(),
                product.getProductName(),
                s3UrlKeyCodec.toUrlOrNull(product.getProductImageKey()),
                product.getSourceType(),
                product.getSourceUrl(),
                product.getSourceText(),
                imageUrls,
                product.getProcessingStatus(),
                product.getAssessmentStatus(),
                product.getResultStatus(),
                product.getSummary(),
                toToolReviewResponses(product.getToolReviews()),
                List.copyOf(product.getRequiredActions()),
                List.copyOf(product.getNotices())
        );
    }

    // 분야별 카드는 저장 순서가 없어 분야(ToolName) 선언 순으로 고정
    private List<ProductToolReviewResponse> toToolReviewResponses(List<ProductToolReview> toolReviews) {
        return toolReviews.stream()
                .sorted(Comparator.comparing(ProductToolReview::getToolName))
                .map(this::toToolReviewResponse)
                .toList();
    }

    private ProductToolReviewResponse toToolReviewResponse(ProductToolReview toolReview) {
        List<ProductFindingResponse> findings = toolReview.getFindings().stream()
                .map(this::toFindingResponse)
                .toList();

        return new ProductToolReviewResponse(
                toolReview.getId(),
                toolReview.getToolName(),
                toolReview.getStatus(),
                toolReview.getMessage(),
                findings
        );
    }

    private ProductFindingResponse toFindingResponse(ProductFinding finding) {
        List<FindingLegalSourceResponse> legalSources = finding.getLegalSources().stream()
                .map(this::toLegalSourceResponse)
                .toList();

        return new ProductFindingResponse(
                finding.getId(),
                finding.getSubject(),
                finding.getDetermination(),
                finding.getRiskLevel(),
                finding.getSummary(),
                finding.getRationale(),
                legalSources
        );
    }

    private FindingLegalSourceResponse toLegalSourceResponse(FindingLegalSource legalSource) {
        return new FindingLegalSourceResponse(
                legalSource.getId(),
                legalSource.getSourceName(),
                legalSource.getLawName(),
                legalSource.getArticle(),
                legalSource.getQuotedText(),
                legalSource.getSourceUrl(),
                legalSource.getEffectiveDate()
        );
    }
}
