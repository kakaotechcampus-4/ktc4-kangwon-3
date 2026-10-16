package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

class ProductTest {

    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String ERROR_CODE = "AI_PIPELINE_ERROR";
    private static final String ERROR_MESSAGE = "진단 중 오류가 발생했습니다.";

    static Stream<Arguments> blankErrors() {
        return Stream.of(
                Arguments.of(null, ERROR_MESSAGE),
                Arguments.of("", ERROR_MESSAGE),
                Arguments.of(" ", ERROR_MESSAGE),
                Arguments.of(ERROR_CODE, null),
                Arguments.of(ERROR_CODE, ""),
                Arguments.of(ERROR_CODE, " ")
        );
    }

    @Test
    @DisplayName("생성된 상품은 대기 상태다.")
    void pending_thenPending() {
        // when
        Product product = createProduct();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
    }

    @Test
    @DisplayName("대기 중인 상품의 진단을 시작하면 진행 중 상태가 된다.")
    void startDiagnosis_whenPending_thenInProgress() {
        // given
        Product product = createProduct();

        // when
        product.startDiagnosis();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이미 진단이 시작된 상품의 진단을 다시 시작하면 CONFLICT 예외가 발생한다.")
    void startDiagnosis_whenInProgress_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertConflict(product::startDiagnosis);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("답변 대기 중인 상품을 재진단하면 진행 중 상태가 된다.")
    void resume_whenAwaitingInput_thenInProgress() {
        // given
        Product product = createAwaitingInputProduct();

        // when
        product.resume();

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("답변 대기 중이 아닌 상품을 재진단하면 CONFLICT 예외가 발생한다.")
    void resume_whenInProgress_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertConflict(product::resume);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("재진단해도 resume 요청에 보낼 이전 실행의 runId는 그대로 남는다.")
    void resume_thenKeepPreviousRunId() {
        // given
        Product product = createInProgressProduct();
        product.assignRun("run-1");
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));

        // when
        product.resume();

        // then
        assertThat(product.getRunId()).isEqualTo("run-1");
    }

    @Test
    @DisplayName("진행 중인 상품이 실행 식별자를 받으면 현재 실행으로 저장된다.")
    void assignRun_whenInProgress_thenAssign() {
        // given
        Product product = createInProgressProduct();

        // when
        product.assignRun("run-1");

        // then
        assertThat(product.getRunId()).isEqualTo("run-1");
        assertThat(product.isCurrentRun("run-1")).isTrue();
    }

    @Test
    @DisplayName("재진단으로 새 실행 식별자를 받으면 교체되고, 이전 실행은 현재 실행이 아니게 된다.")
    void assignRun_whenResumed_thenReplace() {
        // given
        Product product = createInProgressProduct();
        product.assignRun("run-1");
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));
        product.resume();

        // when
        product.assignRun("run-2");

        // then
        assertThat(product.isCurrentRun("run-2")).isTrue();
        assertThat(product.isCurrentRun("run-1")).isFalse();
    }

    @ParameterizedTest(name = "{0}")
    @EnumSource(value = ProcessingStatus.class, mode = EnumSource.Mode.EXCLUDE, names = "IN_PROGRESS")
    @DisplayName("진행 중이 아닌 상품이 실행 식별자를 받으면 CONFLICT 예외가 발생하고 기존 값이 유지된다.")
    void assignRun_whenNotInProgress_thenThrowConflict(ProcessingStatus status) {
        // given
        Product product = createInProgressProduct();
        product.assignRun("run-1");
        ReflectionTestUtils.setField(product, "processingStatus", status);

        // when & then
        assertConflict(() -> product.assignRun("run-2"));
        assertThat(product.getRunId()).isEqualTo("run-1");
    }

    @ParameterizedTest(name = "[{0}]")
    @NullSource
    @ValueSource(strings = {"", " "})
    @DisplayName("비어 있는 실행 식별자를 받으면 BAD_REQUEST 예외가 발생하고 저장되지 않는다.")
    void assignRun_whenBlank_thenThrowBadRequest(String runId) {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.assignRun(runId));
        assertThat(product.getRunId()).isNull();
    }

    @Test
    @DisplayName("실행 식별자를 받기 전에는 어떤 실행도 현재 실행이 아니다.")
    void isCurrentRun_whenNotAssigned_thenFalse() {
        // given: 202를 저장하기 전에 콜백이 먼저 도착한 경우
        Product product = createInProgressProduct();

        // when & then
        assertThat(product.isCurrentRun("run-1")).isFalse();
        assertThat(product.isCurrentRun(null)).isFalse();
    }

    @Test
    @DisplayName("처음 받은 단계의 진행 상태는 새로 추가된다.")
    void recordProgress_whenNew_thenAdd() {
        // given
        Product product = createInProgressProduct();

        // when
        product.recordProgress("run-1", 1, PipelineStage.EXTRACTION, StageStatus.STARTED, null);

        // then
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getRunId, ProductProgress::getSequence, ProductProgress::getStage,
                        ProductProgress::getStageStatus, ProductProgress::getToolName)
                .containsExactly(tuple("run-1", 1, PipelineStage.EXTRACTION, StageStatus.STARTED, null));
        assertThat(product.getProgresses()).allSatisfy(progress -> assertThat(progress.getProduct()).isSameAs(product));
    }

    @Test
    @DisplayName("같은 실행에서 더 뒤의 이벤트가 오면 같은 단계의 행을 갱신한다.")
    void recordProgress_whenNewerSequence_thenUpdate() {
        // given
        Product product = createInProgressProduct();
        product.recordProgress("run-1", 3, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CUSTOMS);

        // when
        product.recordProgress("run-1", 5, PipelineStage.TOOL_EXECUTION, StageStatus.COMPLETED, ToolName.CUSTOMS);

        // then
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getSequence, ProductProgress::getStageStatus)
                .containsExactly(tuple(5, StageStatus.COMPLETED));
    }

    @ParameterizedTest(name = "sequence {0}")
    @ValueSource(ints = {3, 5})
    @DisplayName("같은 실행에서 이미 반영한 것보다 앞서거나 같은 이벤트는 무시한다.")
    void recordProgress_whenOlderOrSameSequence_thenIgnore(int sequence) {
        // given: 재시도로 늦게 도착했거나 중복으로 온 이벤트
        Product product = createInProgressProduct();
        product.recordProgress("run-1", 5, PipelineStage.TOOL_EXECUTION, StageStatus.COMPLETED, ToolName.CUSTOMS);

        // when
        product.recordProgress("run-1", sequence, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CUSTOMS);

        // then
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getSequence, ProductProgress::getStageStatus)
                .containsExactly(tuple(5, StageStatus.COMPLETED));
    }

    @Test
    @DisplayName("새 실행의 이벤트는 sequence가 작아도 이전 실행의 행을 덮어쓴다.")
    void recordProgress_whenNewRun_thenOverwrite() {
        // given: 실행이 바뀌면 sequence가 1부터 다시 시작한다.
        Product product = createInProgressProduct();
        product.recordProgress("run-1", 9, PipelineStage.VERIFICATION, StageStatus.COMPLETED, null);

        // when
        product.recordProgress("run-2", 1, PipelineStage.VERIFICATION, StageStatus.STARTED, null);

        // then
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getRunId, ProductProgress::getSequence, ProductProgress::getStageStatus)
                .containsExactly(tuple("run-2", 1, StageStatus.STARTED));
    }

    @Test
    @DisplayName("같은 툴 실행 단계라도 툴이 다르면 행이 따로 생기고, 툴이 없는 단계와도 구분된다.")
    void recordProgress_whenDifferentTools_thenAddEach() {
        // given
        Product product = createInProgressProduct();

        // when
        product.recordProgress("run-1", 1, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, null);
        product.recordProgress("run-1", 2, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CUSTOMS);
        product.recordProgress("run-1", 3, PipelineStage.TOOL_EXECUTION, StageStatus.SKIPPED, ToolName.RADIO);

        // then
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getToolName, ProductProgress::getStageStatus)
                .containsExactly(
                        tuple(null, StageStatus.STARTED),
                        tuple(ToolName.CUSTOMS, StageStatus.STARTED),
                        tuple(ToolName.RADIO, StageStatus.SKIPPED));
    }

    @Test
    @DisplayName("툴 실행 단계가 아닌데 툴 이름이 오면 BAD_REQUEST 예외가 발생하고 저장되지 않는다.")
    void recordProgress_whenToolNameOutsideToolStage_thenThrowBadRequest() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.recordProgress(
                "run-1", 1, PipelineStage.EXTRACTION, StageStatus.STARTED, ToolName.CUSTOMS));
        assertThat(product.getProgresses()).isEmpty();
    }

    @ParameterizedTest(name = "{0}")
    @EnumSource(value = ProcessingStatus.class, mode = EnumSource.Mode.EXCLUDE, names = "IN_PROGRESS")
    @DisplayName("진행 중이 아닌 상품에 진행 상태를 기록하면 CONFLICT 예외가 발생하고 저장되지 않는다.")
    void recordProgress_whenNotInProgress_thenThrowConflict(ProcessingStatus status) {
        // given: 실행이 끝난 뒤 재시도로 늦게 도착한 진행 이벤트
        Product product = createProduct();
        ReflectionTestUtils.setField(product, "processingStatus", status);

        // when & then
        assertConflict(() -> product.recordProgress(
                "run-1", 1, PipelineStage.EXTRACTION, StageStatus.STARTED, null));
        assertThat(product.getProgresses()).isEmpty();
    }

    @Test
    @DisplayName("진행 중인 상품을 실패 처리하면 실패 상태가 된다.")
    void fail_whenInProgress_thenFailed() {
        // given
        Product product = createInProgressProduct();

        // when
        product.fail(PipelineStage.TOOL_EXECUTION, ERROR_CODE, ERROR_MESSAGE, true);

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(product)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsExactly(PipelineStage.TOOL_EXECUTION, ERROR_CODE, ERROR_MESSAGE, true);
    }

    @Test
    @DisplayName("BE가 직접 실패 처리하면 실패 단계와 재시도 여부 없이 실패 정보가 저장된다.")
    void fail_whenNoStageAndRetryable_thenFailedWithNulls() {
        // given: 멈춘 진단 정리 스케줄러처럼 AI 이벤트 없이 실패 처리하는 경우
        Product product = createInProgressProduct();

        // when
        product.fail(null, "BE_DIAGNOSIS_TIMEOUT", "진단 결과를 받지 못했습니다.", null);

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(product)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsExactly(null, "BE_DIAGNOSIS_TIMEOUT", "진단 결과를 받지 못했습니다.", null);
    }

    @ParameterizedTest(name = "code=[{0}], message=[{1}]")
    @MethodSource("blankErrors")
    @DisplayName("오류 코드나 메시지가 비어 있으면 BAD_REQUEST 예외가 발생하고 상태와 실패 정보가 바뀌지 않는다.")
    void fail_whenBlankError_thenThrowBadRequest(String errorCode, String errorMessage) {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.fail(PipelineStage.EXTRACTION, errorCode, errorMessage, false));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsOnlyNulls();
    }

    @Test
    @DisplayName("답변 대기 중인 상품은 실패 처리할 수 없다.")
    void fail_whenAwaitingInput_thenThrowConflict() {
        // given: 답변 대기는 사용자를 기다리는 정상 상태다.
        Product product = createAwaitingInputProduct();

        // when & then
        assertConflict(() -> product.fail(null, ERROR_CODE, ERROR_MESSAGE, null));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getErrorCode()).isNull();
    }

    @Test
    @DisplayName("이미 실패한 상품을 다시 실패 처리하면 CONFLICT 예외가 발생하고 처음 실패 정보가 유지된다.")
    void fail_whenFailed_thenThrowConflict() {
        // given
        Product product = createInProgressProduct();
        product.fail(PipelineStage.TOOL_EXECUTION, ERROR_CODE, ERROR_MESSAGE, true);

        // when & then
        assertConflict(() -> product.fail(null, "AI_TIMEOUT", "시간이 초과되었습니다.", false));
        assertThat(product)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsExactly(PipelineStage.TOOL_EXECUTION, ERROR_CODE, ERROR_MESSAGE, true);
    }

    @Test
    @DisplayName("진행 중인 상품이 질문을 받으면 답변 없는 질문이 추가되고 답변 대기 상태가 된다.")
    void askQuestions_whenInProgress_thenAddQuestionsAndAwaitInput() {
        // given
        Product product = createInProgressProduct();

        // when
        product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요, 사입해서 파나요?", null),
                new QuestionContent("target_age", 2, "실제로 주로 판매하는 대상 연령은?",
                        "상세페이지에 연령이 함께 적혀 있으면 확인이 필요합니다.")));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey,
                        ProductQuestion::getQuestionOrder, ProductQuestion::isAnswered)
                .containsExactly(tuple(1, "sales_type", 1, false), tuple(1, "target_age", 2, false));
        assertThat(product.getQuestions()).allSatisfy(question -> assertThat(question.getProduct()).isSameAs(product));
    }

    @Test
    @DisplayName("진행 중이 아닌 상품이 질문을 받으면 CONFLICT 예외가 발생하고 질문이 추가되지 않는다.")
    void askQuestions_whenPending_thenThrowConflict() {
        // given
        Product product = createProduct();

        // when & then
        assertConflict(() -> product.askQuestions(1,
                List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null))));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.getQuestions()).isEmpty();
    }

    @Test
    @DisplayName("답변 대기 중인 상품이 다시 질문을 받으면 CONFLICT 예외가 발생하고 질문이 늘지 않는다.")
    void askQuestions_whenAwaitingInput_thenThrowConflict() {
        // given
        Product product = createAwaitingInputProduct();

        // when & then
        assertConflict(() -> product.askQuestions(1,
                List.of(new QuestionContent("target_age", 1, "대상 연령은?", null))));
        assertThat(product.getQuestions()).hasSize(1);
    }

    @Test
    @DisplayName("답변 후 재진단 중인 상품은 다시 질문을 받을 수 있다.")
    void askQuestions_whenResumed_thenAddQuestionsAndAwaitInput() {
        // given: 질문 횟수(최대 2회)는 AI가 제한하므로 BE는 상태만 확인한다.
        Product product = createAwaitingInputProduct();
        product.resume();

        // when
        product.askQuestions(2, List.of(new QuestionContent("target_age", 1, "대상 연령은?", null)));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey)
                .containsExactly(tuple(1, "sales_type"), tuple(2, "target_age"));
    }

    @Test
    @DisplayName("빈 질문 목록을 받으면 BAD_REQUEST 예외가 발생하고 상태가 바뀌지 않는다.")
    void askQuestions_whenEmpty_thenThrowBadRequest() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.askQuestions(1, List.of()));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("같은 키의 질문이 함께 오면 BAD_REQUEST 예외가 발생하고 아무것도 저장되지 않는다.")
    void askQuestions_whenDuplicateKey_thenThrowBadRequest() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertBadRequest(() -> product.askQuestions(1, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null),
                new QuestionContent("sales_type", 2, "사입해서 파나요?", null))));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getQuestions()).isEmpty();
    }

    @Test
    @DisplayName("진행 중인 상품이 완료 결과를 받으면 완료 상태가 되고 결과 카드·판단·근거·조치가 받은 순서대로 채워진다.")
    void complete_whenInProgress_thenCompletedWithResultInOrder() {
        // given
        Product product = createInProgressProduct();
        AssessmentContent content = new AssessmentContent(
                AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                List.of(
                        new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                                List.of(
                                        finding("안전확인 대상 여부", List.of(
                                                legalSource("어린이제품 안전 특별법 시행규칙", "별표 2"),
                                                legalSource("어린이제품 안전 특별법", "제17조"))),
                                        finding("표시사항", List.of()))),
                        new AssessmentContent.ToolReviewContent(ToolName.FOOD_DRUG, ToolReviewStatus.SKIPPED,
                                "식품 접촉 성분이 감지되지 않았습니다.", List.of())),
                List.of("안전확인(KC) 신고 후 판매", "공급사에 시험성적서 요청"),
                List.of());

        // when
        product.complete(content);

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
        assertThat(product.getAssessmentStatus()).isEqualTo(AssessmentStatus.COMPLETED);
        assertThat(product.getResultStatus()).isEqualTo(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED);
        assertThat(product.getSummary()).isEqualTo("사입해서 판매하려면 안전확인(KC)이 필요합니다.");
        assertThat(product.getToolReviews())
                .extracting(ProductToolReview::getToolName, ProductToolReview::getStatus, ProductToolReview::getMessage)
                .containsExactly(
                        tuple(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null),
                        tuple(ToolName.FOOD_DRUG, ToolReviewStatus.SKIPPED, "식품 접촉 성분이 감지되지 않았습니다."));

        ProductToolReview children = product.getToolReviews().getFirst();
        assertThat(children.getFindings())
                .extracting(ProductFinding::getSortOrder, ProductFinding::getSubject)
                .containsExactly(tuple(0, "안전확인 대상 여부"), tuple(1, "표시사항"));
        assertThat(children.getFindings().getFirst().getLegalSources())
                .extracting(FindingLegalSource::getSortOrder, FindingLegalSource::getLawName)
                .containsExactly(tuple(0, "어린이제품 안전 특별법 시행규칙"), tuple(1, "어린이제품 안전 특별법"));
        assertThat(product.getRequiredActions()).containsExactly("안전확인(KC) 신고 후 판매", "공급사에 시험성적서 요청");
        assertThat(product.getNotices()).isEmpty();
        assertThat(product.hasResult()).isTrue();
    }

    @Test
    @DisplayName("안내 문구가 있는 미완료 결과를 받으면 재확인 필요로 완료 상태가 된다.")
    void complete_withIncompleteResult_thenCompletedAsRecheckRequired() {
        // given
        Product product = createInProgressProduct();

        // when
        product.complete(incompleteContent(ResultStatus.RECHECK_REQUIRED, List.of("전파 인증 여부는 확인하지 못했습니다.")));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
        assertThat(product.getAssessmentStatus()).isEqualTo(AssessmentStatus.INCOMPLETE);
        assertThat(product.getResultStatus()).isEqualTo(ResultStatus.RECHECK_REQUIRED);
        assertThat(product.getNotices()).containsExactly("전파 인증 여부는 확인하지 못했습니다.");
    }

    @Test
    @DisplayName("진단을 시작하지 않은 상품이 결과를 받으면 CONFLICT 예외가 발생하고 결과가 채워지지 않는다.")
    void complete_whenPending_thenThrowConflict() {
        // given
        Product product = createProduct();

        // when & then
        assertConflict(() -> product.complete(completedContent(List.of())));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.getResultStatus()).isNull();
    }

    @Test
    @DisplayName("답변 대기 중인 상품이 결과를 받으면 CONFLICT 예외가 발생하고 결과가 채워지지 않는다.")
    void complete_whenAwaitingInput_thenThrowConflict() {
        // given
        Product product = createAwaitingInputProduct();

        // when & then
        assertConflict(() -> product.complete(completedContent(List.of())));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getResultStatus()).isNull();
    }

    @Test
    @DisplayName("결과를 받기 전인 상품은 결과가 없는 것으로 본다.")
    void hasResult_whenInProgress_thenFalse() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertThat(product.hasResult()).isFalse();
    }

    @Test
    @DisplayName("실행 식별자를 받기 전인 상품은 실행이 배정되지 않은 것으로 보고, 받은 뒤에는 배정된 것으로 본다.")
    void isRunAssigned_beforeAndAfterAssignRun() {
        // given
        Product product = createInProgressProduct();

        // when & then
        assertThat(product.isRunAssigned()).isFalse();
        product.assignRun("run-1");
        assertThat(product.isRunAssigned()).isTrue();
    }

    private AssessmentContent completedContent(List<AssessmentContent.ToolReviewContent> toolReviews) {
        return new AssessmentContent(AssessmentStatus.COMPLETED, ResultStatus.PURCHASING_AGENT_ALLOWED,
                "구매대행으로 판매할 수 있습니다.", toolReviews, List.of(), List.of());
    }

    private AssessmentContent incompleteContent(ResultStatus resultStatus, List<String> notices) {
        return new AssessmentContent(AssessmentStatus.INCOMPLETE, resultStatus,
                "일부 항목을 확인하지 못했습니다.", List.of(), List.of(), notices);
    }

    private AssessmentContent.FindingContent finding(String subject,
                                                     List<AssessmentContent.LegalSourceContent> legalSources) {
        return new AssessmentContent.FindingContent(subject, Determination.REQUIRED, RiskLevel.HIGH,
                subject + " 요약", subject + " 근거", legalSources);
    }

    private AssessmentContent.LegalSourceContent legalSource(String lawName, String article) {
        return new AssessmentContent.LegalSourceContent("국가법령정보센터", lawName, article, null, null, null);
    }

    private Product createProduct() {
        return Product.pending(PRODUCT_NAME, null, SourceType.URL, SOURCE_URL, null);
    }

    private Product createInProgressProduct() {
        Product product = createProduct();
        product.startDiagnosis();
        return product;
    }

    private Product createAwaitingInputProduct() {
        Product product = createInProgressProduct();
        product.askQuestions(1, List.of(new QuestionContent("sales_type", 1, "구매대행으로 파나요?", null)));
        return product;
    }

    private void assertConflict(ThrowingCallable action) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.CONFLICT);
    }

    private void assertBadRequest(ThrowingCallable action) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.BAD_REQUEST);
    }
}
