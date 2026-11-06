package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;
import java.util.UUID;

/**
 * 커밋된 뒤 AI에 진단을 요청하기 위한 이벤트.
 * 진단서 생성, 대기 상품 재요청, 실패한 상품 재시도에서 발행한다.
 */
public record AiDiagnosesRequestedEvent(
        UUID diagnosesId,
        List<ProductInput> products
) {

    public static AiDiagnosesRequestedEvent of(UUID diagnosesId, List<Product> products) {
        return new AiDiagnosesRequestedEvent(diagnosesId, products.stream().map(ProductInput::from).toList());
    }

    // imageKeys는 대표 이미지 → 상세 이미지 순서
    public record ProductInput(
            UUID productId,
            SourceType sourceType,
            String sourceUrl,
            String sourceText,
            List<String> imageKeys
    ) {

        static ProductInput from(Product product) {
            return new ProductInput(product.getId(), product.getSourceType(),
                    product.getSourceUrl(), product.getSourceText(), product.collectImageKeys());
        }
    }
}
