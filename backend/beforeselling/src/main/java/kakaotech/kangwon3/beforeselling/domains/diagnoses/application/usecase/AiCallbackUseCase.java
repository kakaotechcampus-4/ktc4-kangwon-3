package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductProgressEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductResultEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.AiCallbackMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class AiCallbackUseCase {

    private final ProductService productService;
    private final AiCallbackMapper aiCallbackMapper;

    public void handleProgress(ProductProgressEvent event) {
        log.debug("AI 진행 콜백 수신. diagnosesId={}, productId={}, eventId={}, runId={}, sequence={}, stage={}, stageStatus={}, toolName={}",
                event.diagnosesId(), event.productId(), event.eventId(), event.runId(), event.sequence(),
                event.stage(), event.stageStatus(), event.toolName());

        productService.recordProgress(event.diagnosesId(), event.productId(), event.runId(), event.sequence(),
                event.stage(), event.stageStatus(), event.toolName());
    }

    public void handleResult(ProductResultEvent event) {
        log.debug("AI 결과 콜백 수신. diagnosesId={}, productId={}, eventId={}, runId={}, sequence={}",
                event.diagnosesId(), event.productId(), event.eventId(), event.runId(), event.sequence());

        productService.completeDiagnoses(event.diagnosesId(), event.productId(), event.runId(),
                aiCallbackMapper.toContent(event.assessment()));
    }
}
