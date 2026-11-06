package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiResumeRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.config.properties.DiagnosesProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * AI가 받지 못한(429·5xx·연결 실패) 재진단 요청을 저장된 답변으로 다시 보낸다.
 * 처음 실패한 뒤 재요청 기한을 넘긴 상품은 실패 처리한다. 한 번 실행에 한 묶음만 처리한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PendingResumeRetryScheduler {

    static final int BATCH_SIZE = 100;

    private final ProductService productService;
    private final AiResumeRequestUseCase aiResumeRequestUseCase;
    private final DiagnosesProperties diagnosesProperties;

    @Scheduled(fixedDelay = 60_000, initialDelay = 60_000)
    public void retryPendingResumes() {
        LocalDateTime deadline = LocalDateTime.now().minus(diagnosesProperties.requestRetryDeadline());
        List<UUID> productIds = productService.findResumePendingProductIds(BATCH_SIZE);

        int requested = 0;
        for (UUID productId : productIds) {
            try {
                Optional<AiResumeRequestedEvent> event = productService.restartPendingResume(productId, deadline);
                if (event.isPresent()) {
                    aiResumeRequestUseCase.requestResume(event.get(), true);
                    requested++;
                }
            } catch (PessimisticLockingFailureException e) {
                log.warn("재진단 재요청 중 락 대기 초과. productId={}", productId);
            } catch (Exception e) {
                log.error("재진단 재요청 실패. productId={}", productId, e);
            }
        }

        if (!productIds.isEmpty()) {
            log.info("재진단 재요청 완료. 대상={}, 재요청={}", productIds.size(), requested);
        }
    }
}
