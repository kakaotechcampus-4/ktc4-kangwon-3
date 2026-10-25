package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiDiagnosesRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class AiDiagnosesRequestEventListenerTest {

    @Mock
    private AiDiagnosesRequestUseCase aiDiagnosesRequestUseCase;

    @InjectMocks
    private AiDiagnosesRequestEventListener listener;

    @Test
    @DisplayName("진단서 생성이 커밋되면 이벤트의 상품들로 AI에 진단을 요청한다.")
    void handle_thenRequestDiagnoses() {
        // given
        AiDiagnosesRequestedEvent event = new AiDiagnosesRequestedEvent(UUID.randomUUID(), List.of(
                new AiDiagnosesRequestedEvent.ProductInput(UUID.randomUUID(), SourceType.TEXT_IMAGE, null,
                        "상세 설명", List.of("product-main/1.jpg"))));

        // when
        listener.handle(event);

        // then
        then(aiDiagnosesRequestUseCase).should().requestDiagnoses(event);
    }
}
