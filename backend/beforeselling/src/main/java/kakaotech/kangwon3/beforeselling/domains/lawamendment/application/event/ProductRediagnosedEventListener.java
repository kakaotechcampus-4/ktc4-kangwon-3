package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.ProductRediagnosedEvent;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import lombok.RequiredArgsConstructor;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * 재진단하면 결과가 새로 나오므로 그 상품을 재확인 대상에서 뺀다.
 * 재진단과 같은 트랜잭션에서 처리해, 하나가 실패하면 둘 다 롤백된다.
 */
@Component
@RequiredArgsConstructor
public class ProductRediagnosedEventListener {

    private final LawAmendmentService lawAmendmentService;

    @EventListener
    public void handle(ProductRediagnosedEvent event) {
        lawAmendmentService.removeRecheckProducts(event.productId());
    }
}
