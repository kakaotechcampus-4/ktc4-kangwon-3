package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.ProductRediagnosedEvent;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class ProductRediagnosedEventListenerTest {

    private static final UUID PRODUCT_ID = UUID.randomUUID();

    @Mock
    private LawAmendmentService lawAmendmentService;

    @InjectMocks
    private ProductRediagnosedEventListener productRediagnosedEventListener;

    @Test
    @DisplayName("재진단 이벤트를 받으면 그 상품을 재확인 대상에서 뺀다.")
    void handle_thenRemoveRecheckProducts() {
        // when
        productRediagnosedEventListener.handle(new ProductRediagnosedEvent(PRODUCT_ID));

        // then
        then(lawAmendmentService).should().removeRecheckProducts(PRODUCT_ID);
    }
}
