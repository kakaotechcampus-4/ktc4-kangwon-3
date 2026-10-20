package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiDiagnosesRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
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
 * AI가 요청을 받지 않아(429, 5xx, 연결 실패) 대기로 되돌린 상품을 다시 요청한다.
 * 재요청 기한을 넘긴 상품은 실패 처리한다. 한 번 실행에 한 묶음만 처리한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PendingDiagnosesRetryScheduler {

    static final int BATCH_SIZE = 100;

    private final ProductService productService;
    private final DiagnosesService diagnosesService;
    private final AiDiagnosesRequestUseCase aiDiagnosesRequestUseCase;
    private final DiagnosesProperties diagnosesProperties;

    @Scheduled(fixedDelay = 60_000, initialDelay = 60_000)
    public void retryPendingDiagnoses() {
        LocalDateTime deadline = LocalDateTime.now().minus(diagnosesProperties.requestRetryDeadline());
        List<UUID> diagnosesIds = productService.findPendingDiagnosesIds(BATCH_SIZE);

        int requested = 0;
        for (UUID diagnosesId : diagnosesIds) {
            try {
                Optional<AiDiagnosesRequestedEvent> event = diagnosesService.restartPendingProducts(diagnosesId, deadline);
                if (event.isPresent()) {
                    aiDiagnosesRequestUseCase.requestDiagnoses(event.get());
                    requested++;
                }
            } catch (PessimisticLockingFailureException e) {
                log.warn("대기 진단 재요청 중 락 대기 초과. diagnosesId={}", diagnosesId);
            } catch (Exception e) {
                log.error("대기 진단 재요청 실패. diagnosesId={}", diagnosesId, e);
            }
        }

        if (!diagnosesIds.isEmpty()) {
            log.info("대기 진단 재요청 완료. 대상={}, 재요청={}", diagnosesIds.size(), requested);
        }
    }
}
