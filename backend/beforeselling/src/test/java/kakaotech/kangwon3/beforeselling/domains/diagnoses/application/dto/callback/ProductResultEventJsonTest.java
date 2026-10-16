package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;
import org.springframework.test.context.ActiveProfiles;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

// AI가 보내는 결과 콜백 JSON이 결과 이벤트로 바뀌는지, 검증 기준이 AI 스키마와 같은지 확인한다.
// Spring이 만든 JsonMapper를 써야 enum 대소문자 무시 설정이 적용된다.
@JsonTest
@ActiveProfiles("test")
class ProductResultEventJsonTest {

    private static final UUID DIAGNOSES_ID = UUID.fromString("01990000-0000-7000-8000-000000000001");
    private static final UUID PRODUCT_ID = UUID.fromString("01990000-0000-7000-8000-000000000002");
    private static final String COMMON_FIELDS = """
            "eventType": "product_result",
            "eventId": "event-1",
            "diagnosisId": "01990000-0000-7000-8000-000000000001",
            "productId": "01990000-0000-7000-8000-000000000002",
            "runId": "run-1",
            "sequence": 14""";

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Autowired
    private JsonMapper jsonMapper;

    @Test
    @DisplayName("결과 콜백 JSON은 소문자 판단 값까지 분야 카드·판단·법령 근거를 가진 결과 이벤트로 바뀐다.")
    void read_whenResult_thenResultEvent() {
        // given
        String json = result("""
                "status": "completed",
                "resultStatus": "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                "summary": "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                "toolReviews": [
                  {
                    "toolName": "CHILDREN",
                    "status": "COMPLETED",
                    "message": null,
                    "findings": [
                      {
                        "subject": "안전확인 대상 여부",
                        "determination": "required",
                        "riskLevel": "high",
                        "summary": "안전확인이 필요합니다.",
                        "rationale": "권장연령 3-6세 기준으로 완구에 해당합니다.",
                        "legalSources": [
                          {
                            "sourceName": "국가법령정보센터",
                            "lawName": "어린이제품 안전 특별법 시행규칙",
                            "article": "별표 2",
                            "quotedText": null,
                            "sourceUrl": "https://www.law.go.kr",
                            "effectiveDate": "2026-01-01"
                          }
                        ]
                      }
                    ]
                  },
                  {"toolName": "FOOD_DRUG", "status": "SKIPPED", "message": "식품 접촉 성분이 없습니다.", "findings": []}
                ],
                "requiredActions": ["안전확인(KC) 신고 후 판매"],
                "notices": []""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isEqualTo(new ProductResultEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 14,
                new PublicAssessmentDto(
                        AssessmentStatus.COMPLETED,
                        ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                        "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                        List.of(
                                new PublicToolReviewDto(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null, List.of(
                                        new PublicFindingDto("안전확인 대상 여부", Determination.REQUIRED, RiskLevel.HIGH,
                                                "안전확인이 필요합니다.", "권장연령 3-6세 기준으로 완구에 해당합니다.",
                                                List.of(new PublicLegalSourceDto("국가법령정보센터",
                                                        "어린이제품 안전 특별법 시행규칙", "별표 2", null,
                                                        "https://www.law.go.kr", "2026-01-01"))))),
                                new PublicToolReviewDto(ToolName.FOOD_DRUG, ToolReviewStatus.SKIPPED,
                                        "식품 접촉 성분이 없습니다.", List.of())),
                        List.of("안전확인(KC) 신고 후 판매"),
                        List.of())));
    }

    @Test
    @DisplayName("미완료 결과 JSON은 소문자 완료 여부를 미완료로 받는다.")
    void read_whenIncompleteResult_thenIncompleteStatus() {
        // given
        String json = result("""
                "status": "incomplete",
                "resultStatus": "RECHECK_REQUIRED",
                "summary": "일부 항목을 확인하지 못했습니다.",
                "toolReviews": [{"toolName": "RADIO", "status": "INCOMPLETE", "findings": []}],
                "requiredActions": [],
                "notices": ["전파 인증 여부는 확인하지 못했습니다."]""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isInstanceOfSatisfying(ProductResultEvent.class, result -> {
            assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.INCOMPLETE);
            assertThat(result.assessment().toolReviews().getFirst().status()).isEqualTo(ToolReviewStatus.INCOMPLETE);
            assertThat(result.assessment().notices()).containsExactly("전파 인증 여부는 확인하지 못했습니다.");
        });
    }

    @Test
    @DisplayName("목록 필드가 빠진 결과 JSON은 빈 목록으로 받는다.")
    void read_whenListFieldsOmitted_thenEmptyLists() {
        // given: AI가 빈 목록을 생략해서 보내도 null 대신 빈 목록으로 다룬다.
        String json = result("""
                "status": "completed",
                "resultStatus": "PURCHASING_AGENT_ALLOWED",
                "summary": "구매대행으로 판매할 수 있습니다.",
                "toolReviews": [
                  {
                    "toolName": "CUSTOMS",
                    "status": "COMPLETED",
                    "findings": [
                      {"subject": "세관장확인", "determination": "not_required", "riskLevel": "low",
                       "summary": "요건이 없습니다.", "rationale": "HS 9503.00 기준입니다."}
                    ]
                  }
                ]""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isInstanceOfSatisfying(ProductResultEvent.class, result -> {
            PublicAssessmentDto assessment = result.assessment();
            assertThat(assessment.requiredActions()).isEmpty();
            assertThat(assessment.notices()).isEmpty();
            PublicFindingDto finding = assessment.toolReviews().getFirst().findings().getFirst();
            assertThat(finding.determination()).isEqualTo(Determination.NOT_REQUIRED);
            assertThat(finding.legalSources()).isEmpty();
        });
    }

    @Test
    @DisplayName("정의되지 않은 판단 값이 오면 거부한다.")
    void read_whenUnknownDetermination_thenThrow() {
        // given
        String json = result("""
                "status": "completed",
                "resultStatus": "PURCHASING_AGENT_ALLOWED",
                "summary": "요약",
                "toolReviews": [
                  {"toolName": "CUSTOMS", "status": "COMPLETED", "findings": [
                    {"subject": "대상", "determination": "maybe", "riskLevel": "low", "summary": "요약", "rationale": "근거"}
                  ]}
                ]""");

        // when & then
        assertThatThrownBy(() -> jsonMapper.readValue(json, ProductEvent.class))
                .isInstanceOf(JacksonException.class);
    }

    @Test
    @DisplayName("올바른 결과 이벤트는 검증을 통과한다.")
    void validate_whenValid_thenNoViolation() {
        assertThat(validator.validate(resultEvent(assessment(List.of(toolReview(List.of(finding(List.of(
                legalSource("국가법령정보센터")))))))))).isEmpty();
    }

    @Test
    @DisplayName("진단 결과가 없으면 위반이다.")
    void validate_whenNoAssessment_thenViolation() {
        assertThat(violatedPaths(resultEvent(null))).containsExactly("assessment");
    }

    @Test
    @DisplayName("결과 완료 여부·결과 상태·요약이 비어 있으면 위반이다.")
    void validate_whenInvalidAssessment_thenViolation() {
        // given
        PublicAssessmentDto assessment = new PublicAssessmentDto(null, null, " ", List.of(), List.of(), List.of());

        // when & then
        assertThat(violatedPaths(resultEvent(assessment)))
                .containsExactlyInAnyOrder("assessment.status", "assessment.resultStatus", "assessment.summary");
    }

    @Test
    @DisplayName("필수 조치·안내 문구 목록 안에 빈 문구가 있으면 위반이다.")
    void validate_whenBlankActionOrNotice_thenViolation() {
        // given
        PublicAssessmentDto assessment = new PublicAssessmentDto(AssessmentStatus.INCOMPLETE,
                ResultStatus.RECHECK_REQUIRED, "요약", List.of(), List.of(" "), List.of(""));

        // when & then
        assertThat(violatedPaths(resultEvent(assessment)))
                .containsExactlyInAnyOrder("assessment.requiredActions[0].<list element>",
                        "assessment.notices[0].<list element>");
    }

    @Test
    @DisplayName("목록 안의 분야 카드도 검증한다(분야·상태 누락).")
    void validate_whenInvalidToolReview_thenViolationOnElement() {
        // given
        PublicToolReviewDto review = new PublicToolReviewDto(null, null, null, List.of());

        // when & then
        assertThat(violatedPaths(resultEvent(assessment(List.of(review)))))
                .containsExactlyInAnyOrder(
                        "assessment.toolReviews[0].toolName", "assessment.toolReviews[0].status");
    }

    @Test
    @DisplayName("카드 안의 판단도 검증한다(대상 255자 초과, 판단·위험 수준 누락, 빈 요약·근거).")
    void validate_whenInvalidFinding_thenViolationOnElement() {
        // given
        PublicFindingDto finding = new PublicFindingDto("가".repeat(256), null, null, " ", "", List.of());

        // when & then
        assertThat(violatedPaths(resultEvent(assessment(List.of(toolReview(List.of(finding)))))))
                .containsExactlyInAnyOrder(
                        "assessment.toolReviews[0].findings[0].subject",
                        "assessment.toolReviews[0].findings[0].determination",
                        "assessment.toolReviews[0].findings[0].riskLevel",
                        "assessment.toolReviews[0].findings[0].summary",
                        "assessment.toolReviews[0].findings[0].rationale");
    }

    @Test
    @DisplayName("판단 안의 법령 근거도 검증한다(빈 출처명, 컬럼 길이 초과).")
    void validate_whenInvalidLegalSource_thenViolationOnElement() {
        // given
        PublicLegalSourceDto source = new PublicLegalSourceDto(" ", "법".repeat(256), "조".repeat(256),
                null, null, "2".repeat(51));

        // when & then
        String path = "assessment.toolReviews[0].findings[0].legalSources[0].";
        assertThat(violatedPaths(resultEvent(assessment(List.of(toolReview(List.of(finding(List.of(source)))))))))
                .containsExactlyInAnyOrder(
                        path + "sourceName", path + "lawName", path + "article", path + "effectiveDate");
    }

    private String result(String assessmentFields) {
        return "{" + COMMON_FIELDS + ", \"assessment\": {" + assessmentFields + "}}";
    }

    private ProductResultEvent resultEvent(PublicAssessmentDto assessment) {
        return new ProductResultEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 1, assessment);
    }

    private PublicAssessmentDto assessment(List<PublicToolReviewDto> toolReviews) {
        return new PublicAssessmentDto(AssessmentStatus.COMPLETED, ResultStatus.PURCHASING_AGENT_ALLOWED,
                "요약", toolReviews, List.of(), List.of());
    }

    private PublicToolReviewDto toolReview(List<PublicFindingDto> findings) {
        return new PublicToolReviewDto(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null, findings);
    }

    private PublicFindingDto finding(List<PublicLegalSourceDto> legalSources) {
        return new PublicFindingDto("대상", Determination.REQUIRED, RiskLevel.HIGH, "요약", "근거", legalSources);
    }

    private PublicLegalSourceDto legalSource(String sourceName) {
        return new PublicLegalSourceDto(sourceName, null, null, null, null, null);
    }

    private List<String> violatedPaths(Object event) {
        Set<ConstraintViolation<Object>> violations = validator.validate(event);
        return violations.stream().map(violation -> violation.getPropertyPath().toString()).toList();
    }
}
