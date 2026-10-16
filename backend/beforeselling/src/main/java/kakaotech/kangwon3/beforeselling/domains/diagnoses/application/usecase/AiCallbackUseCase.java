package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

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

    public void handleResult(ProductResultEvent event) {
        log.debug("AI 결과 콜백 수신. diagnosisId={}, productId={}, eventId={}, runId={}, sequence={}",
                event.diagnosisId(), event.productId(), event.eventId(), event.runId(), event.sequence());

        productService.completeDiagnosis(event.diagnosisId(), event.productId(), event.runId(),
                aiCallbackMapper.toContent(event.assessment()));
    }
}
