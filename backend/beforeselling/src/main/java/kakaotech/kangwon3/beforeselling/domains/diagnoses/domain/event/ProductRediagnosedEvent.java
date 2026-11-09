package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event;

import java.util.UUID;

/**
 * 진단을 마친 상품을 재진단했을 때 발행한다. 재진단과 같은 트랜잭션 안에서 처리된다.
 */
public record ProductRediagnosedEvent(UUID productId) {
}
