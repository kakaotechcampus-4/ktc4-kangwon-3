package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductAwaitingInputEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductFailedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductProgressEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductResultEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicAssessmentDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicErrorDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicFindingDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicLegalSourceDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicQuestionDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicToolReviewDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.AiCallbackMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class AiCallbackUseCaseTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();

    @Mock
    private ProductService productService;

    private AiCallbackUseCase aiCallbackUseCase;

    @BeforeEach
    void setUp() {
        aiCallbackUseCase = new AiCallbackUseCase(productService, new AiCallbackMapper());
    }

    @Test
    @DisplayName("진행 콜백을 받으면 본문의 진단서·상품 id, 실행 식별자, 순번, 단계·툴 진행 상태를 그대로 옮겨 반영을 요청한다.")
    void handleProgress_thenRecordProgressWithSameValues() {
        // given
        ProductProgressEvent event = new ProductProgressEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 3,
                PipelineStage.TOOL_EXECUTION, StageStatus.COMPLETED, ToolName.CHILDREN);

        // when
        aiCallbackUseCase.handleProgress(event);

        // then
        then(productService).should().recordProgress(DIAGNOSES_ID, PRODUCT_ID, "run-1", 3,
                PipelineStage.TOOL_EXECUTION, StageStatus.COMPLETED, ToolName.CHILDREN);
    }

    @Test
    @DisplayName("질문 콜백을 받으면 본문의 진단서·상품 id, 실행 식별자, 회차, 질문 내용을 받은 순서대로 옮겨 반영을 요청한다.")
    void handleAwaitingInput_thenAskQuestionsWithSameContents() {
        // given
        ProductAwaitingInputEvent event = new ProductAwaitingInputEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 5, 2,
                List.of(new PublicQuestionDto("sales_type", 1, "구매대행으로 파나요?", "사입이면 인증이 필요합니다."),
                        new PublicQuestionDto("target_age", 2, "대상 연령은?", null)));

        // when
        aiCallbackUseCase.handleAwaitingInput(event);

        // then
        then(productService).should().askQuestions(DIAGNOSES_ID, PRODUCT_ID, "run-1", 2, List.of(
                new QuestionContent("sales_type", 1, "구매대행으로 파나요?", "사입이면 인증이 필요합니다."),
                new QuestionContent("target_age", 2, "대상 연령은?", null)));
    }

    @Test
    @DisplayName("실패 콜백을 받으면 본문의 실패 단계와 오류 코드·메시지·재시도 여부를 그대로 옮겨 실패 처리를 요청한다.")
    void handleFailed_thenFailDiagnosesWithSameError() {
        // given
        ProductFailedEvent event = new ProductFailedEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 7,
                PipelineStage.VERIFICATION, new PublicErrorDto("AI_TIMEOUT", "시간이 초과되었습니다.", true));

        // when
        aiCallbackUseCase.handleFailed(event);

        // then
        then(productService).should().failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, "run-1", PipelineStage.VERIFICATION,
                "AI_TIMEOUT", "시간이 초과되었습니다.", true);
    }

    @Test
    @DisplayName("결과 콜백을 받으면 본문의 진단서·상품 id, 실행 식별자, 결과 내용을 그대로 옮겨 반영을 요청한다.")
    void handleResult_thenCompleteDiagnosesWithSameContent() {
        // given
        ProductResultEvent event = resultEvent();

        // when
        aiCallbackUseCase.handleResult(event);

        // then
        ArgumentCaptor<AssessmentContent> captor = ArgumentCaptor.forClass(AssessmentContent.class);
        then(productService).should().completeDiagnoses(eq(DIAGNOSES_ID), eq(PRODUCT_ID), eq("run-1"), captor.capture());

        assertThat(captor.getValue()).isEqualTo(new AssessmentContent(
                AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                List.of(new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                        List.of(new AssessmentContent.FindingContent("안전확인 대상 여부", Determination.REQUIRED,
                                RiskLevel.HIGH, "안전확인이 필요합니다.", "완구에 해당합니다.",
                                List.of(new AssessmentContent.LegalSourceContent("국가법령정보센터",
                                        "어린이제품 안전 특별법 시행규칙", "별표 2", null,
                                        "https://www.law.go.kr", "2026-01-01")))))),
                List.of("안전확인(KC) 신고 후 판매"),
                List.of("전파 인증 여부는 확인하지 못했습니다.")));
    }

    private ProductResultEvent resultEvent() {
        PublicAssessmentDto assessment = new PublicAssessmentDto(
                AssessmentStatus.COMPLETED,
                ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                List.of(new PublicToolReviewDto(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                        List.of(new PublicFindingDto("안전확인 대상 여부", Determination.REQUIRED, RiskLevel.HIGH,
                                "안전확인이 필요합니다.", "완구에 해당합니다.",
                                List.of(new PublicLegalSourceDto("국가법령정보센터", "어린이제품 안전 특별법 시행규칙",
                                        "별표 2", null, "https://www.law.go.kr", "2026-01-01")))))),
                List.of("안전확인(KC) 신고 후 판매"),
                List.of("전파 인증 여부는 확인하지 못했습니다."));
        return new ProductResultEvent("event-1", DIAGNOSES_ID, PRODUCT_ID, "run-1", 14, assessment);
    }
}
