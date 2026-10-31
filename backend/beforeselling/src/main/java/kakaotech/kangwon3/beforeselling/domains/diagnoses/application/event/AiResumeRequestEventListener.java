package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiResumeRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * 사용자 답변이 커밋된 뒤 AI에 재진단을 요청한다. 요청 결과 처리는 AiResumeRequestUseCase 참고.
 */
@Component
@RequiredArgsConstructor
public class AiResumeRequestEventListener {

    private final AiResumeRequestUseCase aiResumeRequestUseCase;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(AiResumeRequestedEvent event) {
        aiResumeRequestUseCase.requestResume(event, false);
    }
}
