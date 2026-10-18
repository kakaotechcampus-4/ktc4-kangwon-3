package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.FindingLegalSourceResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductFindingResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductToolReviewResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductFinding;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductToolReview;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
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
import static org.assertj.core.api.Assertions.tuple;
import java.util.UUID;

class ProductMapperTest {

    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID_2 = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID = UUID.randomUUID(); // 추가
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

    // 추가
    @Test
    @DisplayName("목록 카드로 변환하면 상품이 속한 진단서 ID가 담긴다.")
    void toSummaryResponse_thenIncludeDiagnosesId() {
        // given & when
        ProductSummaryResponse response = productMapper.toSummaryResponse(
                createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null));

        // then
        assertThat(response.diagnosesId()).isEqualTo(DIAGNOSES_ID);
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

    @Test
    @DisplayName("상세로 변환하면 원본 입력과 이미지 URL이 등록 순서대로 담긴다.")
    void toResponse_thenIncludeSourceAndImageUrlsInOrder() {
        // given
        Product product = createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null);
        product.addImages(List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));

        // when
        ProductResponse response = productMapper.toResponse(product);

        // then
        assertThat(response.productId()).isEqualTo(PRODUCT_ID);
        assertThat(response.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(response.productImageUrl()).isEqualTo(URL_PREFIX + PRODUCT_IMAGE_KEY);
        assertThat(response.sourceType()).isEqualTo(SourceType.URL);
        assertThat(response.sourceUrl()).isEqualTo(SOURCE_URL);
        assertThat(response.imageUrls()).containsExactly(
                URL_PREFIX + "product-detail/1/uuid_a1.jpg",
                URL_PREFIX + "product-detail/1/uuid_a2.jpg");
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(response.resultStatus()).isNull();
        assertThat(response.summary()).isNull();
    }

    @Test
    @DisplayName("상세 이미지와 대표 이미지 없이 등록한 상품을 변환하면 이미지가 비어 있다.")
    void toResponse_withoutImages_thenImagesAreEmpty() {
        // given & when
        ProductResponse response = productMapper.toResponse(
                createProduct(PRODUCT_ID, null, SourceType.URL, null));

        // then
        assertThat(response.productImageUrl()).isNull();
        assertThat(response.imageUrls()).isEmpty();
    }

    @Test
    @DisplayName("판정이 끝난 상품을 상세로 변환하면 진단 결과와 요약이 함께 담긴다.")
    void toResponse_withResult_thenIncludeResultAndSummary() {
        // given
        Product product = createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, ResultStatus.RECHECK_REQUIRED);
        ReflectionTestUtils.setField(product, "summary", "배터리 표시 항목 재확인이 필요합니다.");

        // when
        ProductResponse response = productMapper.toResponse(product);

        // then
        assertThat(response.resultStatus()).isEqualTo(ResultStatus.RECHECK_REQUIRED);
        assertThat(response.summary()).isEqualTo("배터리 표시 항목 재확인이 필요합니다.");
    }

    @Test
    @DisplayName("진단이 완료된 상품을 상세로 변환하면 분야별 카드와 판단 항목, 법령 근거, 필요한 조치, 안내 사항이 담긴다.")
    void toResponse_withCompletedAssessment_thenIncludeToolReviewsAndFindingsAndLegalSources() {
        // given
        Product product = createCompletedProduct(List.of(childrenReview()));
        ProductToolReview review = product.getToolReviews().getFirst();
        ProductFinding finding = review.getFindings().getFirst();
        UUID toolReviewId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        UUID legalSourceId = UUID.randomUUID();
        ReflectionTestUtils.setField(review, "id", toolReviewId);
        ReflectionTestUtils.setField(finding, "id", findingId);
        ReflectionTestUtils.setField(finding.getLegalSources().getFirst(), "id", legalSourceId);

        // when
        ProductResponse response = productMapper.toResponse(product);

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
        assertThat(response.assessmentStatus()).isEqualTo(AssessmentStatus.COMPLETED);
        assertThat(response.resultStatus()).isEqualTo(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED);
        assertThat(response.summary()).isEqualTo("사입해서 판매하려면 안전확인(KC)이 필요합니다.");
        assertThat(response.requiredActions()).containsExactly("안전확인 신고", "사용연령 표시");
        assertThat(response.notices()).containsExactly("구매대행으로 판매하면 결론이 달라질 수 있습니다.");

        ProductToolReviewResponse toolReview = response.toolReviews().getFirst();
        assertThat(toolReview.productToolReviewId()).isEqualTo(toolReviewId);
        assertThat(toolReview.toolName()).isEqualTo(ToolName.CHILDREN);
        assertThat(toolReview.status()).isEqualTo(ToolReviewStatus.COMPLETED);
        assertThat(toolReview.findings())
                .extracting(ProductFindingResponse::productFindingId, ProductFindingResponse::subject,
                        ProductFindingResponse::determination, ProductFindingResponse::riskLevel)
                .containsExactly(
                        tuple(findingId, "안전확인 대상 여부", Determination.REQUIRED, RiskLevel.HIGH),
                        tuple(null, "표시사항", Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM));

        ProductFindingResponse certification = toolReview.findings().getFirst();
        assertThat(certification.summary()).isEqualTo("안전확인이 필요합니다.");
        assertThat(certification.rationale()).isEqualTo("권장연령 3-6세 기준으로 완구에 해당합니다.");
        assertThat(certification.legalSources())
                .extracting(FindingLegalSourceResponse::findingLegalSourceId, FindingLegalSourceResponse::lawName,
                        FindingLegalSourceResponse::article, FindingLegalSourceResponse::effectiveDate)
                .containsExactly(
                        tuple(legalSourceId, "어린이제품 안전 특별법 시행규칙", "별표 2", "2026-01-01"),
                        tuple(null, "어린이제품 안전 특별법", "제17조", null));
    }

    @Test
    @DisplayName("분야별 카드는 결과에 담긴 순서와 관계없이 정해진 분야 순서대로 담긴다.")
    void toResponse_withToolReviewsOutOfOrder_thenSortByToolName() {
        // given: 정해진 분야 순서(CUSTOMS → CHILDREN → ... → LABEL_AD)와 반대로 담는다.
        Product product = createCompletedProduct(List.of(
                skippedReview(ToolName.LABEL_AD),
                childrenReview(),
                skippedReview(ToolName.CUSTOMS)));

        // when
        ProductResponse response = productMapper.toResponse(product);

        // then
        assertThat(response.toolReviews())
                .extracting(ProductToolReviewResponse::toolName)
                .containsExactly(ToolName.CUSTOMS, ToolName.CHILDREN, ToolName.LABEL_AD);
    }

    @Test
    @DisplayName("진단이 끝나지 않은 상품을 상세로 변환하면 결과 상태는 비어 있고 결과 목록은 빈 목록이다.")
    void toResponse_withoutAssessment_thenResultListsAreEmpty() {
        // given & when
        ProductResponse response = productMapper.toResponse(
                createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null));

        // then
        assertThat(response.assessmentStatus()).isNull();
        assertThat(response.toolReviews()).isEmpty();
        assertThat(response.requiredActions()).isEmpty();
        assertThat(response.notices()).isEmpty();
    }

    private Product createCompletedProduct(List<AssessmentContent.ToolReviewContent> toolReviews) {
        Product product = createProduct(PRODUCT_ID, PRODUCT_IMAGE_KEY, SourceType.URL, null);
        product.startDiagnoses();
        product.complete(new AssessmentContent(
                AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                toolReviews,
                List.of("안전확인 신고", "사용연령 표시"),
                List.of("구매대행으로 판매하면 결론이 달라질 수 있습니다.")));
        return product;
    }

    private AssessmentContent.ToolReviewContent childrenReview() {
        return new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null, List.of(
                new AssessmentContent.FindingContent("안전확인 대상 여부", Determination.REQUIRED, RiskLevel.HIGH,
                        "안전확인이 필요합니다.", "권장연령 3-6세 기준으로 완구에 해당합니다.", List.of(
                        new AssessmentContent.LegalSourceContent("국가법령정보센터", "어린이제품 안전 특별법 시행규칙",
                                "별표 2", "완구: 14세 미만의 어린이가 놀이용으로 사용하는 제품",
                                "https://www.law.go.kr", "2026-01-01"),
                        new AssessmentContent.LegalSourceContent("국가법령정보센터", "어린이제품 안전 특별법",
                                "제17조", null, null, null))),
                new AssessmentContent.FindingContent("표시사항", Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM,
                        "사용연령 표시를 확인해야 합니다.", "상세페이지에 사용연령 표기가 없습니다.", List.of())));
    }

    private AssessmentContent.ToolReviewContent skippedReview(ToolName toolName) {
        return new AssessmentContent.ToolReviewContent(toolName, ToolReviewStatus.SKIPPED,
                "해당하지 않아 검토하지 않았습니다.", List.of());
    }

    private Product createProduct(UUID productId, String productImageKey,
                                  SourceType sourceType, ResultStatus resultStatus) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        Product product = Product.pending(PRODUCT_NAME, productImageKey, sourceType, SOURCE_URL, null);
        diagnoses.addProducts(List.of(product));

        ReflectionTestUtils.setField(diagnoses, "id", DIAGNOSES_ID); // 추가
        ReflectionTestUtils.setField(product, "id", productId);
        ReflectionTestUtils.setField(product, "createdAt", LocalDateTime.now());
        ReflectionTestUtils.setField(product, "updatedAt", LocalDateTime.now());
        if (resultStatus != null) {
            ReflectionTestUtils.setField(product, "resultStatus", resultStatus);
        }
        return product;
    }
}