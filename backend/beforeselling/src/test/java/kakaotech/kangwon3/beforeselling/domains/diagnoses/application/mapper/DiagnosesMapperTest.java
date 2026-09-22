package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductCreateCommand;
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

class DiagnosesMapperTest {

    private static final Long USER_ID = 1L;
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String URL_PREFIX = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/";

    private final DiagnosesMapper diagnosesMapper = new DiagnosesMapper(new S3UrlKeyCodec(new S3Properties(
            "test-bucket", "ap-northeast-2",
            Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"), null)));

    @Test
    @DisplayName("진단 요청을 변환하면 상품마다 커맨드가 요청 순서대로 만들어진다.")
    void toCommands_thenKeepRequestOrder() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(List.of(
                productRequest("상품 A", List.of("product-detail/1/uuid_a1.jpg")),
                productRequest("상품 B", List.of())));

        // when
        List<ProductCreateCommand> commands = diagnosesMapper.toCommands(request);

        // then
        assertThat(commands).extracting(ProductCreateCommand::productName)
                .containsExactly("상품 A", "상품 B");

        ProductCreateCommand first = commands.getFirst();
        assertThat(first.productImageKey()).isEqualTo(PRODUCT_IMAGE_KEY);
        assertThat(first.sourceType()).isEqualTo(SourceType.URL);
        assertThat(first.sourceUrl()).isEqualTo(SOURCE_URL);
        assertThat(first.imageKeys()).containsExactly("product-detail/1/uuid_a1.jpg");
    }

    @Test
    @DisplayName("이미지 없이 상품을 요청하면 이미지 목록이 빈 값으로 변환된다.")
    void toCommands_withoutImageKeys_thenReturnEmptyList() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(List.of(
                new ProductCreateRequest(PRODUCT_NAME, null, SourceType.URL, SOURCE_URL, null, null)));

        // when
        List<ProductCreateCommand> commands = diagnosesMapper.toCommands(request);

        // then
        assertThat(commands.getFirst().imageKeys()).isNotNull().isEmpty();
    }

    @Test
    @DisplayName("진단 요청 생성 응답으로 변환하면 진단서 ID가 담긴다.")
    void toCreateResponse_thenIncludeDiagnosesId() {
        // given & when
        DiagnosesCreateResponse response = diagnosesMapper.toCreateResponse(createDiagnoses(42L, PRODUCT_IMAGE_KEY));

        // then
        assertThat(response.diagnosesId()).isEqualTo(42L);
    }

    @Test
    @DisplayName("진단서 상세로 변환하면 저장된 key가 접근 가능한 URL로 조립된다.")
    void toDetailResponse_thenConvertKeysToUrls() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L, PRODUCT_IMAGE_KEY);
        diagnoses.getProducts().getFirst()
                .addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.diagnosesId()).isEqualTo(1L);
        assertThat(response.products()).hasSize(1);

        ProductResponse product = response.products().getFirst();
        assertThat(product.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(product.productImageUrl()).isEqualTo(URL_PREFIX + PRODUCT_IMAGE_KEY);
        assertThat(product.imageUrls()).containsExactly(
                URL_PREFIX + "product-detail/1/uuid_a1.jpg",
                URL_PREFIX + "product-detail/1/uuid_a2.jpg");
    }

    @Test
    @DisplayName("상품 여러 개를 담은 진단서를 변환하면 정렬 값과 함께 모두 반환된다.")
    void toDetailResponse_withMultipleProducts_thenIncludeAllInOrder() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L, PRODUCT_IMAGE_KEY, "상품 A", "상품 B", "상품 C");

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.products())
                .extracting(ProductResponse::productName, ProductResponse::sortOrder)
                .containsExactly(
                        org.assertj.core.api.Assertions.tuple("상품 A", 0),
                        org.assertj.core.api.Assertions.tuple("상품 B", 1),
                        org.assertj.core.api.Assertions.tuple("상품 C", 2));
    }

    @Test
    @DisplayName("대표 이미지 없이 등록한 상품을 변환하면 대표 이미지 URL이 비어 있다.")
    void toDetailResponse_withoutProductImageKey_thenProductImageUrlIsNull() {
        // given & when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(createDiagnoses(1L, null));

        // then
        assertThat(response.products().getFirst().productImageUrl()).isNull();
    }

    @Test
    @DisplayName("진단이 완료되지 않은 진단서를 변환하면 진단 결과가 비어 있다.")
    void toDetailResponse_withPendingDiagnoses_thenResultIsEmpty() {
        // given & when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(createDiagnoses(1L, PRODUCT_IMAGE_KEY));

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);

        ProductResponse product = response.products().getFirst();
        assertThat(product.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.resultStatus()).isNull();
        assertThat(product.summary()).isNull();
        assertThat(product.imageUrls()).isEmpty();
    }

    @Test
    @DisplayName("목록 카드로 변환하면 상품 수와 대표 상품 정보가 담긴다.")
    void toSummaryResponse_thenIncludeProductCountAndRepresentative() {
        // given & when
        DiagnosesSummaryResponse response = diagnosesMapper.toSummaryResponse(
                createDiagnoses(1L, PRODUCT_IMAGE_KEY, "상품 A", "상품 B"));

        // then
        assertThat(response.diagnosesId()).isEqualTo(1L);
        assertThat(response.productCount()).isEqualTo(2);
        assertThat(response.representativeProductName()).isEqualTo("상품 A");
        assertThat(response.representativeProductImageUrl()).isEqualTo(URL_PREFIX + PRODUCT_IMAGE_KEY);
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
    }

    @Test
    @DisplayName("대표 이미지 없이 등록한 진단서를 목록 카드로 변환하면 썸네일이 비어 있다.")
    void toSummaryResponse_withoutProductImageKey_thenThumbnailIsNull() {
        // given & when
        DiagnosesSummaryResponse response = diagnosesMapper.toSummaryResponse(createDiagnoses(1L, null));

        // then
        assertThat(response.representativeProductImageUrl()).isNull();
    }

    @Test
    @DisplayName("상품이 하나도 없는 진단서를 목록 카드로 변환해도 예외 없이 빈 값이 담긴다.")
    void toSummaryResponse_withoutProducts_thenRepresentativeIsNull() {
        // given
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        ReflectionTestUtils.setField(diagnoses, "id", 1L);
        ReflectionTestUtils.setField(diagnoses, "createdAt", LocalDateTime.now());

        // when
        DiagnosesSummaryResponse response = diagnosesMapper.toSummaryResponse(diagnoses);

        // then
        assertThat(response.productCount()).isZero();
        assertThat(response.representativeProductName()).isNull();
        assertThat(response.representativeProductImageUrl()).isNull();
    }

    @Test
    @DisplayName("목록으로 변환하면 진단서 요약과 페이징 정보가 함께 담긴다.")
    void toListResponse_thenIncludeSummariesAndPageInfo() {
        // given
        Page<Diagnoses> page = new PageImpl<>(
                List.of(createDiagnoses(1L, PRODUCT_IMAGE_KEY), createDiagnoses(2L, PRODUCT_IMAGE_KEY)),
                PageRequest.of(0, 2),
                5);

        // when
        DiagnosesListResponse response = diagnosesMapper.toListResponse(page);

        // then
        assertThat(response.diagnoses())
                .extracting(DiagnosesSummaryResponse::diagnosesId)
                .containsExactly(1L, 2L);

        DiagnosesListResponse.PageInfo pageInfo = response.pageInfo();
        assertThat(pageInfo.page()).isZero();
        assertThat(pageInfo.size()).isEqualTo(2);
        assertThat(pageInfo.totalElements()).isEqualTo(5);
        assertThat(pageInfo.totalPages()).isEqualTo(3);
        assertThat(pageInfo.hasNext()).isTrue();
    }

    private ProductCreateRequest productRequest(String productName, List<String> imageKeys) {
        return new ProductCreateRequest(
                productName, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null, imageKeys);
    }

    private Diagnoses createDiagnoses(Long diagnosesId, String productImageKey) {
        return createDiagnoses(diagnosesId, productImageKey, PRODUCT_NAME);
    }

    private Diagnoses createDiagnoses(Long diagnosesId, String productImageKey, String... productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        ReflectionTestUtils.setField(diagnoses, "id", diagnosesId);
        ReflectionTestUtils.setField(diagnoses, "createdAt", LocalDateTime.now());
        ReflectionTestUtils.setField(diagnoses, "updatedAt", LocalDateTime.now());

        diagnoses.addProducts(List.of(productNames).stream()
                .map(name -> Product.pending(name, productImageKey, SourceType.URL, SOURCE_URL, null))
                .toList());

        return diagnoses;
    }
}
