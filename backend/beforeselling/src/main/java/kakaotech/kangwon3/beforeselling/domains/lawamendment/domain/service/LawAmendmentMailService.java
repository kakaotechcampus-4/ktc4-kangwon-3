package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.infra.mail.MailTemplate;
import kakaotech.kangwon3.beforeselling.global.infra.mail.event.MailSendRequestedEvent;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Slf4j
@Service
@Transactional(readOnly = true)
public class LawAmendmentMailService {

    private static final String DEFAULT_REVISION_TYPE = "개정";

    private final UserService userService;
    private final ApplicationEventPublisher eventPublisher;
    private final String productsUrl;

    public LawAmendmentMailService(UserService userService, ApplicationEventPublisher eventPublisher,
                                   @Value("${app.mail.products-url}") String productsUrl) {
        this.userService = userService;
        this.eventPublisher = eventPublisher;
        this.productsUrl = productsUrl;
    }

    /**
     * 재확인 대상 상품을 가진 회원에게 개정 알림 메일을 전송
     * 변경이 여러 건이어도 회원당 한 건으로 묶어 전송
     */
    public void sendLawAmendmentMails(Map<LawAmendment, List<Product>> recheckProductsByAmendment) {
        Map<UUID, Set<LawAmendment>> amendmentsByUserId = new HashMap<>();
        Map<UUID, Set<Product>> productsByUserId = new HashMap<>();
        recheckProductsByAmendment.forEach((lawAmendment, products) -> products.forEach(product -> {
            UUID userId = product.getDiagnoses().getUserId();
            amendmentsByUserId.computeIfAbsent(userId, key -> new LinkedHashSet<>()).add(lawAmendment);
            productsByUserId.computeIfAbsent(userId, key -> new HashSet<>()).add(product);
        }));

        List<User> recipients = userService.getUsers(amendmentsByUserId.keySet()).stream()
                .filter(User::isLawAmendmentAlertEnabled)
                .toList();
        recipients.forEach(user -> eventPublisher.publishEvent(new MailSendRequestedEvent(
                user.getEmail(), MailTemplate.LAW_AMENDMENT,
                variables(amendmentsByUserId.get(user.getId()), productsByUserId.get(user.getId()).size()))));

        log.info("개정 알림 메일 발송 요청. lawAmendmentCount={}, userCount={}, recipientCount={}",
                recheckProductsByAmendment.size(), amendmentsByUserId.size(), recipients.size());
    }

    private Map<String, Object> variables(Set<LawAmendment> lawAmendments, long affectedProductCount) {
        return Map.of(
                "laws", lawAmendments.stream().map(this::law).toList(),
                "affectedProductCount", affectedProductCount,
                "productsUrl", productsUrl);
    }

    private Map<String, Object> law(LawAmendment lawAmendment) {
        LocalDate amendedOn = lawAmendment.getEnforceDate() != null ? lawAmendment.getEnforceDate() : LocalDate.now();
        String revisionType = lawAmendment.getRevisionType() != null
                ? lawAmendment.getRevisionType() : DEFAULT_REVISION_TYPE;

        return Map.of(
                "lawName", lawAmendment.getLawName(),
                "revisionType", revisionType,
                "amendedOn", amendedOn.toString());
    }
}
