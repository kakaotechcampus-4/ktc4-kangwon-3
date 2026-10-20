package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductCreateCommand;
import kakaotech.kangwon3.beforeselling.global.config.properties.DiagnosesProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.util.unit.DataSize;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.UUID;

class DiagnosesMapperTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID USER_ID = UUID.randomUUID();
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String URL_PREFIX = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/";

    private final S3UrlKeyCodec s3UrlKeyCodec = new S3UrlKeyCodec(new S3Properties(
            "test-bucket", "ap-northeast-2",
            Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"), null));

    private final DiagnosesMapper diagnosesMapper = new DiagnosesMapper(new ProductMapper(s3UrlKeyCodec),
            new DiagnosesProperties(Duration.ofMinutes(15), Duration.ofSeconds(3)));

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
        DiagnosesCreateResponse response = diagnosesMapper.toCreateResponse(createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY));

        // then
        assertThat(response.diagnosesId()).isEqualTo(DIAGNOSES_ID);
    }

    @Test
    @DisplayName("진단서 상세로 변환하면 저장된 key가 접근 가능한 URL로 조립된다.")
    void toDetailResponse_thenConvertKeysToUrls() {
        // given
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY);
        diagnoses.getProducts().getFirst()
                .addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(response.products()).hasSize(1);

        ProductResponse product = response.products().getFirst();
        assertThat(product.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(product.productImageUrl()).isEqualTo(URL_PREFIX + PRODUCT_IMAGE_KEY);
        assertThat(product.imageUrls()).containsExactly(
                URL_PREFIX + "product-detail/1/uuid_a1.jpg",
                URL_PREFIX + "product-detail/1/uuid_a2.jpg");
    }

    @Test
    @DisplayName("상품 여러 개를 담은 진단서를 변환하면 등록한 순서대로 모두 반환된다.")
    void toDetailResponse_withMultipleProducts_thenIncludeAllInOrder() {
        // given
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY, "상품 A", "상품 B", "상품 C");

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.products())
                .extracting(ProductResponse::productName)
                .containsExactly("상품 A", "상품 B", "상품 C");
    }

    @Test
    @DisplayName("대표 이미지 없이 등록한 상품을 변환하면 대표 이미지 URL이 비어 있다.")
    void toDetailResponse_withoutProductImageKey_thenProductImageUrlIsNull() {
        // given & when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(createDiagnoses(DIAGNOSES_ID, null));

        // then
        assertThat(response.products().getFirst().productImageUrl()).isNull();
    }

    @Test
    @DisplayName("진단이 완료되지 않은 진단서를 변환하면 진단 결과가 비어 있다.")
    void toDetailResponse_withPendingDiagnoses_thenResultIsEmpty() {
        // given & when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY));

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);

        ProductResponse product = response.products().getFirst();
        assertThat(product.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.resultStatus()).isNull();
        assertThat(product.summary()).isNull();
        assertThat(product.imageUrls()).isEmpty();
    }

    @Test
    @DisplayName("진단 중인 상품이 있으면 설정한 폴링 간격을 ms로 담는다.")
    void toDetailResponse_withProcessingProduct_thenIncludePollInterval() {
        // given
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY);
        diagnoses.startDiagnoses();

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.pollIntervalMs()).isEqualTo(3000L);
    }

    @Test
    @DisplayName("한 상품이 답변 대기여도 다른 상품이 진행 중이면 진단서 상태와 관계없이 폴링 간격을 담는다.")
    void toDetailResponse_withAwaitingInputAndInProgress_thenIncludePollInterval() {
        // given
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY, "상품 A", "상품 B");
        diagnoses.startDiagnoses();
        diagnoses.getProducts().getFirst().askQuestions(1, List.of(question()));
        diagnoses.refreshProcessingStatus();

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(response.pollIntervalMs()).isEqualTo(3000L);
    }

    @Test
    @DisplayName("진단 중인 상품이 없으면(답변 대기·실패만 남음) 폴링 간격이 비어 폴링을 멈추게 한다.")
    void toDetailResponse_withoutProcessingProduct_thenPollIntervalIsNull() {
        // given
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID, PRODUCT_IMAGE_KEY, "상품 A", "상품 B");
        diagnoses.startDiagnoses();
        diagnoses.getProducts().getFirst().askQuestions(1, List.of(question()));
        diagnoses.getProducts().get(1).fail(null, "AI_TIMEOUT", "시간이 초과되었습니다.", true);
        diagnoses.refreshProcessingStatus();

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses);

        // then
        assertThat(response.pollIntervalMs()).isNull();
    }

    private QuestionContent question() {
        return new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null);
    }

    private ProductCreateRequest productRequest(String productName, List<String> imageKeys) {
        return new ProductCreateRequest(
                productName, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null, imageKeys);
    }

    private Diagnoses createDiagnoses(UUID diagnosesId, String productImageKey) {
        return createDiagnoses(diagnosesId, productImageKey, PRODUCT_NAME);
    }

    private Diagnoses createDiagnoses(UUID diagnosesId, String productImageKey, String... productNames) {
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
