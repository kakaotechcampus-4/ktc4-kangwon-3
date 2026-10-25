package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiDiagnosesRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * 진단서 생성이 커밋된 뒤 AI에 진단을 요청한다. 요청 결과 처리는 AiDiagnosesRequestUseCase 참고.
 */
@Component
@RequiredArgsConstructor
public class AiDiagnosesRequestEventListener {

    private final AiDiagnosesRequestUseCase aiDiagnosesRequestUseCase;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(AiDiagnosesRequestedEvent event) {
        aiDiagnosesRequestUseCase.requestDiagnoses(event);
    }
}
