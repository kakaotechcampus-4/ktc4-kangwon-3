package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.config.properties.DiagnosesProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * AI 콜백이 끝내 오지 않아 진행 중으로 멈춘 진단을 실패 처리한다.
 * 한 번 실행에 한 묶음만 처리한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StuckDiagnosesScheduler {

    static final int BATCH_SIZE = 100;

    private final ProductService productService;
    private final DiagnosesProperties diagnosesProperties;

    @Scheduled(fixedDelay = 60_000, initialDelay = 60_000)
    public void failStuckDiagnoses() {
        LocalDateTime threshold = LocalDateTime.now().minus(diagnosesProperties.stuckThreshold());
        List<UUID> productIds = productService.findStuckProductIds(threshold, BATCH_SIZE);

        int failed = 0;
        for (UUID productId : productIds) {
            try {
                if (productService.failStuckDiagnoses(productId, threshold)) {
                    failed++;
                }
            } catch (PessimisticLockingFailureException e) {
                // 콜백이 같은 진단서를 처리 중이다. 다음 실행에서 다시 확인한다.
                log.warn("멈춘 진단 처리 중 락 대기 초과. productId={}", productId);
            } catch (Exception e) {
                log.error("멈춘 진단 처리 실패. productId={}", productId, e);
            }
        }

        if (!productIds.isEmpty()) {
            log.info("멈춘 진단 정리 완료. 대상={}, 실패 처리={}", productIds.size(), failed);
        }
    }
}
