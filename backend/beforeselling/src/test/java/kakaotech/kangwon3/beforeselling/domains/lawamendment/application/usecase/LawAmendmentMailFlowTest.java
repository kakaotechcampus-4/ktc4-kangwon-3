package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentProductRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentRepository;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.repository.UserRepository;
import kakaotech.kangwon3.beforeselling.global.infra.mail.MailMessage;
import kakaotech.kangwon3.beforeselling.global.infra.mail.MailSender;
import kakaotech.kangwon3.beforeselling.global.infra.mail.MailTemplate;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.time.LocalDate;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.after;
import static org.mockito.Mockito.timeout;

/**
 * 법령 변경 콜백부터 재확인 대상 지정, 커밋 뒤 비동기 메일 발송까지 실제 DB와 트랜잭션으로 확인한다.
 * 메일 발송부만 목으로 둔다.
 */
@Tag("integration")
@SpringBootTest
@ActiveProfiles("test")
class LawAmendmentMailFlowTest {

    @Autowired
    private LawAmendmentCallbackUseCase lawAmendmentCallbackUseCase;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private LawAmendmentRepository lawAmendmentRepository;

    @Autowired
    private LawAmendmentProductRepository lawAmendmentProductRepository;

    @MockitoBean
    private MailSender mailSender;

    @AfterEach
    void tearDown() {
        lawAmendmentProductRepository.deleteAll();
        lawAmendmentRepository.deleteAll();
        diagnosesRepository.deleteAll();
        userRepository.deleteAll();
    }

    @Test
    @DisplayName("법령 변경을 받으면 커밋 뒤 재확인 대상 상품을 가진 회원에게만 개정 알림 메일을 보낸다.")
    void receiveLawChanges_thenSendMailAfterCommit() {
        // given
        User user = userRepository.save(User.socialSignup(SocialProvider.KAKAO, "social-1", "user@example.com", "홍길동"));
        User disabled = User.socialSignup(SocialProvider.KAKAO, "social-2", "off@example.com", "김철수");
        disabled.updateLawAmendmentAlertEnabled(false);
        disabled = userRepository.save(disabled);
        saveCompletedProduct(user.getId());
        saveCompletedProduct(disabled.getId());

        // when
        lawAmendmentCallbackUseCase.receiveLawChanges(new LawChangeCallbackRequest(List.of(
                new PublicLawChangeDto("어린이제품 안전 특별법 시행규칙", "012345", false,
                        ToolName.CHILDREN, "291321", "280000", "일부개정",
                        LocalDate.of(2026, 10, 20), LocalDate.of(2026, 4, 20)))));

        // then
        ArgumentCaptor<MailMessage> captor = ArgumentCaptor.forClass(MailMessage.class);
        then(mailSender).should(timeout(3000)).send(captor.capture());
        then(mailSender).should(after(500).times(1)).send(captor.capture());
        MailMessage message = captor.getValue();
        assertThat(message.to()).isEqualTo("user@example.com");
        assertThat(message.subject()).isEqualTo(MailTemplate.LAW_AMENDMENT.getSubject());
        assertThat(message.textBody())
                .contains("2026-10-20", "어린이제품 안전 특별법 시행규칙", "1개", "http://localhost:5173/products");
        assertThat(lawAmendmentProductRepository.count()).isEqualTo(2);
    }

    @Test
    @DisplayName("한 번에 받은 변경 여러 건이 같은 회원 상품에 걸리면 법령을 모아 메일 한 통만 보낸다.")
    void receiveLawChanges_withManyChanges_thenSendOneMailPerUser() {
        // given
        User user = userRepository.save(User.socialSignup(SocialProvider.KAKAO, "social-1", "user@example.com", "홍길동"));
        saveCompletedProduct(user.getId(), "어린이제품 안전 특별법", "어린이제품 안전 특별법 시행규칙");

        // when
        lawAmendmentCallbackUseCase.receiveLawChanges(new LawChangeCallbackRequest(List.of(
                new PublicLawChangeDto("어린이제품 안전 특별법", "012344", false,
                        ToolName.CHILDREN, "291320", "280001", "일부개정",
                        LocalDate.of(2026, 10, 20), LocalDate.of(2026, 4, 20)),
                new PublicLawChangeDto("어린이제품 안전 특별법 시행규칙", "012345", false,
                        ToolName.CHILDREN, "291321", "280000", "일부개정",
                        LocalDate.of(2026, 10, 20), LocalDate.of(2026, 4, 20)))));

        // then
        ArgumentCaptor<MailMessage> captor = ArgumentCaptor.forClass(MailMessage.class);
        then(mailSender).should(timeout(3000)).send(captor.capture());
        then(mailSender).should(after(500).times(1)).send(captor.capture());
        assertThat(captor.getValue().textBody())
                .contains("어린이제품 안전 특별법 (", "어린이제품 안전 특별법 시행규칙 (", "상품이 1개");
        assertThat(lawAmendmentProductRepository.count()).isEqualTo(2);
    }

    private void saveCompletedProduct(UUID userId) {
        saveCompletedProduct(userId, "어린이제품 안전 특별법 시행규칙");
    }

    private void saveCompletedProduct(UUID userId, String... citedLawNames) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(List.of(Product.pending("대나무 헬리콥터", null, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null)));
        diagnoses.startDiagnoses();
        Product product = diagnoses.getProducts().getFirst();
        product.assignRun("run-1");
        product.complete(new AssessmentContent(AssessmentStatus.COMPLETED, ResultStatus.PURCHASING_AGENT_ALLOWED,
                "구매대행으로 판매할 수 있습니다.",
                List.of(new AssessmentContent.ToolReviewContent(ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                        List.of(new AssessmentContent.FindingContent("판단", Determination.REQUIRED, RiskLevel.HIGH,
                                "요약", "근거", Arrays.stream(citedLawNames)
                                .map(lawName -> new AssessmentContent.LegalSourceContent(
                                        "법제처 국가법령정보", lawName, "별표 1", null, null, null))
                                .toList())))),
                List.of(), List.of()));
        diagnoses.refreshProcessingStatus();
        diagnosesRepository.save(diagnoses);
    }
}
