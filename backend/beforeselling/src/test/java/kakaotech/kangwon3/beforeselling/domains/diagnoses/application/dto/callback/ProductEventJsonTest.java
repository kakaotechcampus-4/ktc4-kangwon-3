package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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

// AI가 보내는 콜백 JSON이 이벤트 DTO로 바뀌는지, 검증 기준이 AI 스키마와 같은지 확인한다.
// Spring이 만든 JsonMapper를 써야 enum 대소문자 무시 설정이 적용된다.
@JsonTest
@ActiveProfiles("test")
class ProductEventJsonTest {

    private static final UUID DIAGNOSIS_ID = UUID.fromString("01990000-0000-7000-8000-000000000001");
    private static final UUID PRODUCT_ID = UUID.fromString("01990000-0000-7000-8000-000000000002");
    private static final String COMMON_FIELDS = """
            "eventId": "event-1",
            "diagnosisId": "01990000-0000-7000-8000-000000000001",
            "productId": "01990000-0000-7000-8000-000000000002",
            "runId": "run-1",
            "sequence": 3""";

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Autowired
    private JsonMapper jsonMapper;

    @Test
    @DisplayName("진행 콜백 JSON은 소문자 단계 값까지 진행 이벤트로 바뀐다.")
    void read_whenProgress_thenProgressEvent() {
        // given
        String json = event("product_progress", """
                "stage": "tool_execution",
                "stageStatus": "started",
                "toolName": "CUSTOMS\"""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isEqualTo(new ProductProgressEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 3,
                PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CUSTOMS));
    }

    @ParameterizedTest(name = "{0}")
    @ValueSource(strings = {"", ", \"toolName\": null"})
    @DisplayName("툴 단계가 아닌 진행 콜백은 toolName이 없거나 null이어도 받는다.")
    void read_whenProgressWithoutToolName_thenNull(String toolName) {
        // given
        String json = event("product_progress", """
                "stage": "extraction",
                "stageStatus": "completed\"""" + toolName);

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isInstanceOfSatisfying(ProductProgressEvent.class, progress -> {
            assertThat(progress.stage()).isEqualTo(PipelineStage.EXTRACTION);
            assertThat(progress.toolName()).isNull();
        });
    }

    @Test
    @DisplayName("질문 콜백 JSON은 회차와 질문 목록을 가진 질문 이벤트로 바뀐다.")
    void read_whenAwaitingInput_thenAwaitingInputEvent() {
        // given
        String json = event("product_awaiting_input", """
                "questionRound": 2,
                "questions": [
                  {"questionKey": "sales_type", "questionOrder": 1, "questionText": "구매대행으로 파나요?", "helpText": "판매 방식"},
                  {"questionKey": "target_age", "questionOrder": 2, "questionText": "대상 연령은?"}
                ]""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isEqualTo(new ProductAwaitingInputEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 3, 2,
                List.of(new PublicQuestionDto("sales_type", 1, "구매대행으로 파나요?", "판매 방식"),
                        new PublicQuestionDto("target_age", 2, "대상 연령은?", null))));
    }

    @Test
    @DisplayName("실패 콜백 JSON은 실패 단계와 오류 정보를 가진 실패 이벤트로 바뀐다.")
    void read_whenFailed_thenFailedEvent() {
        // given
        String json = event("product_failed", """
                "stage": "verification",
                "error": {"code": "AI_TIMEOUT", "message": "시간이 초과되었습니다.", "retryable": true}""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isEqualTo(new ProductFailedEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 3,
                PipelineStage.VERIFICATION, new PublicErrorDto("AI_TIMEOUT", "시간이 초과되었습니다.", true)));
    }

    @Test
    @DisplayName("실패 단계와 재시도 여부가 없으면 null로 받고, 재시도 여부를 false로 바꾸지 않는다.")
    void read_whenFailedWithoutStageAndRetryable_thenNull() {
        // given: 공개하지 않는 내부 단계에서 실패했고 AI가 재시도 여부를 판단하지 않은 경우
        String json = event("product_failed", """
                "error": {"code": "AI_PIPELINE_ERROR", "message": "진단 중 오류가 발생했습니다."}""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isInstanceOfSatisfying(ProductFailedEvent.class, failed -> {
            assertThat(failed.stage()).isNull();
            assertThat(failed.error().retryable()).isNull();
        });
    }

    @Test
    @DisplayName("AI가 BE가 모르는 필드를 추가해도 콜백을 받는다.")
    void read_whenUnknownField_thenIgnore() {
        // given: AI가 필드를 추가했다고 콜백 전체가 400이 되면 진단이 멈춘다.
        String json = event("product_progress", """
                "stage": "selection",
                "stageStatus": "started",
                "newField": "added later\"""");

        // when
        ProductEvent event = jsonMapper.readValue(json, ProductEvent.class);

        // then
        assertThat(event).isInstanceOf(ProductProgressEvent.class);
    }

    @Test
    @DisplayName("정의되지 않은 eventType은 거부한다.")
    void read_whenUnsupportedEventType_thenThrow() {
        // given
        String json = event("product_unknown", """
                "stage": "selection",
                "stageStatus": "started\"""");

        // when & then
        assertThatThrownBy(() -> jsonMapper.readValue(json, ProductEvent.class))
                .isInstanceOf(JacksonException.class);
    }

    @Test
    @DisplayName("eventType이 없으면 이벤트 종류를 알 수 없어 거부한다.")
    void read_whenNoEventType_thenThrow() {
        // given
        String json = "{" + COMMON_FIELDS + ", \"stage\": \"selection\", \"stageStatus\": \"started\"}";

        // when & then
        assertThatThrownBy(() -> jsonMapper.readValue(json, ProductEvent.class))
                .isInstanceOf(JacksonException.class);
    }

    @Test
    @DisplayName("상품 ID가 UUID 형식이 아니면 거부한다.")
    void read_whenInvalidUuid_thenThrow() {
        // given
        String json = event("product_progress", """
                "stage": "selection",
                "stageStatus": "started\"""").replace(PRODUCT_ID.toString(), "not-a-uuid");

        // when & then
        assertThatThrownBy(() -> jsonMapper.readValue(json, ProductEvent.class))
                .isInstanceOf(JacksonException.class);
    }

    @Test
    @DisplayName("올바른 이벤트는 검증을 통과한다.")
    void validate_whenValid_thenNoViolation() {
        assertThat(validator.validate(progress("event-1", 1, PipelineStage.EXTRACTION))).isEmpty();
        assertThat(validator.validate(awaitingInput(1, List.of(question("sales_type"))))).isEmpty();
        assertThat(validator.validate(failed(new PublicErrorDto("AI_TIMEOUT", "시간 초과", null)))).isEmpty();
    }

    @Test
    @DisplayName("공통 필드가 비었거나 순서가 1보다 작으면 위반이다.")
    void validate_whenInvalidCommonFields_thenViolation() {
        // given
        ProductProgressEvent event = new ProductProgressEvent(" ", null, PRODUCT_ID, "", 0,
                null, StageStatus.STARTED, null);

        // when & then
        assertThat(violatedPaths(event))
                .containsExactlyInAnyOrder("eventId", "diagnosisId", "runId", "sequence", "stage");
    }

    @ParameterizedTest(name = "questionRound={0}")
    @ValueSource(ints = {0, 3})
    @DisplayName("질문 회차가 1~2를 벗어나면 위반이다.")
    void validate_whenQuestionRoundOutOfRange_thenViolation(int questionRound) {
        assertThat(violatedPaths(awaitingInput(questionRound, List.of(question("sales_type")))))
                .containsExactly("questionRound");
    }

    @Test
    @DisplayName("질문 목록이 비어 있으면 위반이다.")
    void validate_whenNoQuestions_thenViolation() {
        assertThat(violatedPaths(awaitingInput(1, List.of()))).containsExactly("questions");
    }

    @Test
    @DisplayName("목록 안의 질문도 검증한다(키 50자 초과, 빈 문구, 순서 0).")
    void validate_whenInvalidQuestion_thenViolationOnElement() {
        // given
        PublicQuestionDto question = new PublicQuestionDto("k".repeat(51), 0, " ", null);

        // when & then
        assertThat(violatedPaths(awaitingInput(1, List.of(question))))
                .containsExactlyInAnyOrder(
                        "questions[0].questionKey", "questions[0].questionOrder", "questions[0].questionText");
    }

    @Test
    @DisplayName("실패 이벤트에 오류 정보가 없으면 위반이다.")
    void validate_whenNoError_thenViolation() {
        assertThat(violatedPaths(failed(null))).containsExactly("error");
    }

    @Test
    @DisplayName("오류 코드가 50자를 넘거나 오류 코드·메시지가 비어 있으면 위반이다.")
    void validate_whenInvalidError_thenViolationOnError() {
        assertThat(violatedPaths(failed(new PublicErrorDto("E".repeat(51), "메시지", null))))
                .containsExactly("error.code");
        assertThat(violatedPaths(failed(new PublicErrorDto(" ", "", null))))
                .containsExactlyInAnyOrder("error.code", "error.message");
    }

    private String event(String eventType, String fields) {
        return "{\"eventType\": \"" + eventType + "\", " + COMMON_FIELDS + ", " + fields + "}";
    }

    private ProductProgressEvent progress(String eventId, int sequence, PipelineStage stage) {
        return new ProductProgressEvent(eventId, DIAGNOSIS_ID, PRODUCT_ID, "run-1", sequence,
                stage, StageStatus.STARTED, null);
    }

    private ProductAwaitingInputEvent awaitingInput(int questionRound, List<PublicQuestionDto> questions) {
        return new ProductAwaitingInputEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 1,
                questionRound, questions);
    }

    private ProductFailedEvent failed(PublicErrorDto error) {
        return new ProductFailedEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 1, null, error);
    }

    private PublicQuestionDto question(String questionKey) {
        return new PublicQuestionDto(questionKey, 1, "질문", null);
    }

    private List<String> violatedPaths(Object event) {
        Set<ConstraintViolation<Object>> violations = validator.validate(event);
        return violations.stream().map(violation -> violation.getPropertyPath().toString()).toList();
    }
}
