package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.infra.mail.MailTemplate;
import kakaotech.kangwon3.beforeselling.global.infra.mail.event.MailSendRequestedEvent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.times;

@ExtendWith(MockitoExtension.class)
class LawAmendmentMailServiceTest {

    private static final String MY_PAGE_URL = "http://localhost:5173/mypage";
    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();

    @Mock
    private UserService userService;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    private LawAmendmentMailService lawAmendmentMailService;

    @BeforeEach
    void setUp() {
        lawAmendmentMailService = new LawAmendmentMailService(userService, eventPublisher, MY_PAGE_URL);
    }

    @Test
    @DisplayName("재확인 대상 상품을 가진 회원에게 법령 목록·상품 수를 담은 개정 알림 메일을 보낸다.")
    void sendLawAmendmentMails_thenPublishMailWithVariables() {
        // given
        LawAmendment lawAmendment = lawAmendment("어린이제품 안전 특별법 시행규칙", "일부개정", LocalDate.of(2026, 10, 20));
        given(userService.getUsers(Set.of(USER_ID))).willReturn(List.of(user(USER_ID, "user@example.com")));

        // when
        lawAmendmentMailService.sendLawAmendmentMails(Map.of(lawAmendment, List.of(product(USER_ID), product(USER_ID))));

        // then
        ArgumentCaptor<MailSendRequestedEvent> captor = ArgumentCaptor.forClass(MailSendRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        MailSendRequestedEvent event = captor.getValue();
        assertThat(event.to()).isEqualTo("user@example.com");
        assertThat(event.template()).isEqualTo(MailTemplate.LAW_AMENDMENT);
        assertThat(event.variables())
                .containsEntry("laws", List.of(Map.of(
                        "lawName", "어린이제품 안전 특별법 시행규칙",
                        "revisionType", "일부개정",
                        "amendedOn", "2026-10-20")))
                .containsEntry("affectedProductCount", 2L)
                .containsEntry("myPageUrl", MY_PAGE_URL);
    }

    @Test
    @DisplayName("한 번에 받은 변경 여러 건이 같은 회원에게 걸리면 법령을 모아 메일 한 통만 보내고, 상품은 한 번씩만 센다.")
    void sendLawAmendmentMails_withManyAmendments_thenOneMailPerUser() {
        // given
        LawAmendment act = lawAmendment("화장품법", "일부개정", LocalDate.of(2026, 10, 20));
        LawAmendment rule = lawAmendment("화장품법 시행규칙", "일부개정", LocalDate.of(2026, 10, 21));
        Product citesBoth = product(USER_ID);
        Product citesRule = product(USER_ID);
        Map<LawAmendment, List<Product>> recheckProducts = new LinkedHashMap<>();
        recheckProducts.put(act, List.of(citesBoth));
        recheckProducts.put(rule, List.of(citesBoth, citesRule));
        given(userService.getUsers(Set.of(USER_ID))).willReturn(List.of(user(USER_ID, "user@example.com")));

        // when
        lawAmendmentMailService.sendLawAmendmentMails(recheckProducts);

        // then
        ArgumentCaptor<MailSendRequestedEvent> captor = ArgumentCaptor.forClass(MailSendRequestedEvent.class);
        then(eventPublisher).should(times(1)).publishEvent(captor.capture());
        assertThat(captor.getValue().variables())
                .containsEntry("laws", List.of(
                        Map.of("lawName", "화장품법", "revisionType", "일부개정", "amendedOn", "2026-10-20"),
                        Map.of("lawName", "화장품법 시행규칙", "revisionType", "일부개정", "amendedOn", "2026-10-21")))
                .containsEntry("affectedProductCount", 2L);
    }

    @Test
    @DisplayName("회원마다 자기 상품에 걸린 법령만 담아 보낸다.")
    void sendLawAmendmentMails_withManyUsers_thenOnlyOwnLaws() {
        // given
        LawAmendment act = lawAmendment("화장품법", "일부개정", LocalDate.of(2026, 10, 20));
        LawAmendment rule = lawAmendment("화장품법 시행규칙", "일부개정", LocalDate.of(2026, 10, 21));
        Map<LawAmendment, List<Product>> recheckProducts = new LinkedHashMap<>();
        recheckProducts.put(act, List.of(product(USER_ID)));
        recheckProducts.put(rule, List.of(product(OTHER_USER_ID)));
        given(userService.getUsers(Set.of(USER_ID, OTHER_USER_ID)))
                .willReturn(List.of(user(USER_ID, "user@example.com"), user(OTHER_USER_ID, "other@example.com")));

        // when
        lawAmendmentMailService.sendLawAmendmentMails(recheckProducts);

        // then
        ArgumentCaptor<MailSendRequestedEvent> captor = ArgumentCaptor.forClass(MailSendRequestedEvent.class);
        then(eventPublisher).should(times(2)).publishEvent(captor.capture());
        assertThat(captor.getAllValues())
                .extracting(MailSendRequestedEvent::to, event -> lawNames(event))
                .containsExactlyInAnyOrder(
                        tuple("user@example.com", List.of("화장품법")),
                        tuple("other@example.com", List.of("화장품법 시행규칙")));
    }

    @Test
    @DisplayName("제개정구분과 시행일을 모르면 개정과 오늘 날짜로 알린다.")
    void sendLawAmendmentMails_withoutRevisionTypeAndEnforceDate_thenDefault() {
        // given
        LawAmendment lawAmendment = lawAmendment("어린이제품 안전 특별법 시행규칙", null, null);
        given(userService.getUsers(Set.of(USER_ID))).willReturn(List.of(user(USER_ID, "user@example.com")));

        // when
        lawAmendmentMailService.sendLawAmendmentMails(Map.of(lawAmendment, List.of(product(USER_ID))));

        // then
        ArgumentCaptor<MailSendRequestedEvent> captor = ArgumentCaptor.forClass(MailSendRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        assertThat(captor.getValue().variables())
                .containsEntry("laws", List.of(Map.of(
                        "lawName", "어린이제품 안전 특별법 시행규칙",
                        "revisionType", "개정",
                        "amendedOn", LocalDate.now().toString())));
    }

    @Test
    @DisplayName("개정 알림을 끈 회원에게는 메일을 보내지 않는다.")
    void sendLawAmendmentMails_whenAlertDisabled_thenSkip() {
        // given
        User enabled = user(USER_ID, "user@example.com");
        User disabled = user(OTHER_USER_ID, "other@example.com");
        disabled.updateLawAmendmentAlertEnabled(false);
        given(userService.getUsers(Set.of(USER_ID, OTHER_USER_ID))).willReturn(List.of(enabled, disabled));

        // when
        lawAmendmentMailService.sendLawAmendmentMails(Map.of(
                lawAmendment("어린이제품 안전 특별법 시행규칙", "일부개정", LocalDate.of(2026, 10, 20)),
                List.of(product(USER_ID), product(OTHER_USER_ID))));

        // then
        ArgumentCaptor<MailSendRequestedEvent> captor = ArgumentCaptor.forClass(MailSendRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        assertThat(captor.getValue().to()).isEqualTo("user@example.com");
    }

    @Test
    @DisplayName("탈퇴해 회원 정보가 없으면 메일을 보내지 않는다.")
    void sendLawAmendmentMails_whenUserWithdrawn_thenSkip() {
        // given
        given(userService.getUsers(Set.of(USER_ID))).willReturn(List.of());

        // when
        lawAmendmentMailService.sendLawAmendmentMails(Map.of(
                lawAmendment("어린이제품 안전 특별법 시행규칙", "일부개정", LocalDate.of(2026, 10, 20)),
                List.of(product(USER_ID))));

        // then
        then(eventPublisher).should(never()).publishEvent(any());
    }

    @SuppressWarnings("unchecked")
    private List<Object> lawNames(MailSendRequestedEvent event) {
        return ((List<Map<String, Object>>) event.variables().get("laws")).stream()
                .map(law -> law.get("lawName"))
                .toList();
    }

    private LawAmendment lawAmendment(String lawName, String revisionType, LocalDate enforceDate) {
        return LawAmendment.builder()
                .lawName(lawName)
                .documentId("012345")
                .toolName(ToolName.CHILDREN)
                .serialNumber("291321")
                .revisionType(revisionType)
                .enforceDate(enforceDate)
                .build();
    }

    private Product product(UUID userId) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(List.of(Product.pending("대나무 헬리콥터", null, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null)));
        return diagnoses.getProducts().getFirst();
    }

    private User user(UUID userId, String email) {
        User user = User.socialSignup(SocialProvider.KAKAO, userId.toString(), email, "홍길동");
        ReflectionTestUtils.setField(user, "id", userId);
        return user;
    }
}
