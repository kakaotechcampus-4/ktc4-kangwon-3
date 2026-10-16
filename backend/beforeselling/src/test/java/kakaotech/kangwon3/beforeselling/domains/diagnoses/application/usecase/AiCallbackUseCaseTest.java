package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductResultEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicAssessmentDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicFindingDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicLegalSourceDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicToolReviewDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.AiCallbackMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
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

    private static final UUID DIAGNOSIS_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();

    @Mock
    private ProductService productService;

    private AiCallbackUseCase aiCallbackUseCase;

    @BeforeEach
    void setUp() {
        aiCallbackUseCase = new AiCallbackUseCase(productService, new AiCallbackMapper());
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
        then(productService).should().completeDiagnoses(eq(DIAGNOSIS_ID), eq(PRODUCT_ID), eq("run-1"), captor.capture());

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
        return new ProductResultEvent("event-1", DIAGNOSIS_ID, PRODUCT_ID, "run-1", 14, assessment);
    }
}
