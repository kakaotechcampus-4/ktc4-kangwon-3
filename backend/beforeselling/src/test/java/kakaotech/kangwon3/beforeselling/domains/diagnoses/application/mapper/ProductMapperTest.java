package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.util.unit.DataSize;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.UUID;

class ProductMapperTest {

    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID_2 = UUID.randomUUID();
    private static final UUID USER_ID = UUID.randomUUID();
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String URL_PREFIX = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/";

    private final ProductMapper productMapper = new ProductMapper(new S3UrlKeyCodec(new S3Properties(
            "test-bucket", "ap-northeast-2",
            Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"), null)));

    @Test
    @DisplayName("목록 카드로 변환하면 썸네일 URL과 입력 방식, 상태 값이 담긴다.")
    void toSummaryResponse_thenIncludeThumbnailAndSourceTypeAndStatus() {
        // given & when
        ProductSummaryResponse response = productMapper.toSummaryResponse(
                createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null));

        // then
        assertThat(response.productId()).isEqualTo(PRODUCT_ID);
        assertThat(response.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(response.productImageUrl()).isEqualTo(URL_PREFIX + PRODUCT_IMAGE_KEY);
        assertThat(response.sourceType()).isEqualTo(SourceType.URL);
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(response.resultStatus()).isNull();
        assertThat(response.createdAt()).isNotNull();
    }

    @Test
    @DisplayName("텍스트·이미지로 등록한 상품을 변환하면 입력 방식이 TEXT_IMAGE로 담긴다.")
    void toSummaryResponse_withTextImageType_thenKeepSourceType() {
        // given & when
        ProductSummaryResponse response = productMapper.toSummaryResponse(
                createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.TEXT_IMAGE, null));

        // then
        assertThat(response.sourceType()).isEqualTo(SourceType.TEXT_IMAGE);
    }

    @Test
    @DisplayName("대표 이미지 없이 등록한 상품을 변환하면 썸네일이 비어 있다.")
    void toSummaryResponse_withoutProductImageKey_thenThumbnailIsNull() {
        // given & when
        ProductSummaryResponse response = productMapper.toSummaryResponse(
                createProduct(PRODUCT_ID, null, SourceType.URL, null));

        // then
        assertThat(response.productImageUrl()).isNull();
    }

    @Test
    @DisplayName("판정이 끝난 상품을 변환하면 진단 결과가 함께 담긴다.")
    void toSummaryResponse_withResultStatus_thenIncludeResult() {
        // given & when
        ProductSummaryResponse response = productMapper.toSummaryResponse(
                createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, ResultStatus.RECHECK_REQUIRED));

        // then
        assertThat(response.resultStatus()).isEqualTo(ResultStatus.RECHECK_REQUIRED);
    }

    @Test
    @DisplayName("목록으로 변환하면 상품 요약과 페이징 정보가 함께 담긴다.")
    void toListResponse_thenIncludeSummariesAndPageInfo() {
        // given
        Page<Product> page = new PageImpl<>(
                List.of(createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null),
                        createProduct(PRODUCT_ID_2, PRODUCT_IMAGE_KEY, SourceType.TEXT_IMAGE, null)),
                PageRequest.of(0, 2),
                5);

        // when
        ProductListResponse response = productMapper.toListResponse(page);

        // then
        assertThat(response.products())
                .extracting(ProductSummaryResponse::productId)
                .containsExactly(PRODUCT_ID, PRODUCT_ID_2);

        assertThat(response.pageInfo().page()).isZero();
        assertThat(response.pageInfo().size()).isEqualTo(2);
        assertThat(response.pageInfo().totalElements()).isEqualTo(5);
        assertThat(response.pageInfo().totalPages()).isEqualTo(3);
        assertThat(response.pageInfo().hasNext()).isTrue();
    }

    private Product createProduct(UUID productId, String productImageKey,
                                  SourceType sourceType, ResultStatus resultStatus) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = Product.pending(PRODUCT_NAME, productImageKey, sourceType, SOURCE_URL, null);
        diagnoses.addProducts(List.of(product));

        ReflectionTestUtils.setField(product, "id", productId);
        ReflectionTestUtils.setField(product, "createdAt", LocalDateTime.now());
        ReflectionTestUtils.setField(product, "updatedAt", LocalDateTime.now());
        if (resultStatus != null) {
            ReflectionTestUtils.setField(product, "resultStatus", resultStatus);
        }
        return product;
    }
}
