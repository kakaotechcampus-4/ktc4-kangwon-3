package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class AiDiagnosesRequestedEventTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();

    @Test
    @DisplayName("상품으로 이벤트를 만들면 상품마다 입력 내용과 이미지 key를 순서대로 담는다.")
    void of_thenContainProductInputsInOrder() {
        // given
        Product urlProduct = createProduct("대나무 헬리콥터", SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null, "thumb-1.jpg", List.of("detail-1.jpg", "detail-2.jpg"));
        Product textProduct = createProduct("만능 우산", SourceType.TEXT_IMAGE,
                null, "상세페이지 내용", null, List.of());

        // when
        AiDiagnosesRequestedEvent event = AiDiagnosesRequestedEvent.of(DIAGNOSES_ID, List.of(urlProduct, textProduct));

        // then
        assertThat(event.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(event.products())
                .extracting(AiDiagnosesRequestedEvent.ProductInput::productId,
                        AiDiagnosesRequestedEvent.ProductInput::sourceType,
                        AiDiagnosesRequestedEvent.ProductInput::sourceUrl,
                        AiDiagnosesRequestedEvent.ProductInput::sourceText,
                        AiDiagnosesRequestedEvent.ProductInput::imageKeys)
                .containsExactly(
                        tuple(urlProduct.getId(), SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null,
                                List.of("thumb-1.jpg", "detail-1.jpg", "detail-2.jpg")),
                        tuple(textProduct.getId(), SourceType.TEXT_IMAGE, null, "상세페이지 내용", List.of()));
    }

    private Product createProduct(String productName, SourceType sourceType, String sourceUrl, String sourceText,
                                  String productImageKey, List<String> imageKeys) {
        Product product = Product.pending(productName, productImageKey, sourceType, sourceUrl, sourceText);
        product.addImages(imageKeys);
        ReflectionTestUtils.setField(product, "id", UUID.randomUUID());
        return product;
    }
}
