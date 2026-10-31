package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiResumeRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
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
class AiResumeRequestEventListenerTest {

    @Mock
    private AiResumeRequestUseCase aiResumeRequestUseCase;

    @InjectMocks
    private AiResumeRequestEventListener listener;

    @Test
    @DisplayName("답변이 커밋되면 처음 보내는 재진단 요청으로 처리한다.")
    void handle_thenRequestResumeAsFirstSend() {
        // given
        AiResumeRequestedEvent event = new AiResumeRequestedEvent(UUID.randomUUID(), UUID.randomUUID(), "run-1", 1,
                List.of(new AiResumeRequestedEvent.Answer("sales_type", "구매대행")));

        // when
        listener.handle(event);

        // then
        then(aiResumeRequestUseCase).should().requestResume(event, false);
    }
}
