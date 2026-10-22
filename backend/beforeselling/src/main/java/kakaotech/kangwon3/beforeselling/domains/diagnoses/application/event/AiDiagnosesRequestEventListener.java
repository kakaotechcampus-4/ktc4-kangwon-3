package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 진단서 생성이 커밋된 뒤 AI에 진단을 요청하고, 접수 응답(202)의 상품별 실행 식별자를 저장한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiDiagnosesRequestEventListener {

    private final AiDiagnosesClient aiDiagnosesClient;
    private final S3UrlKeyCodec s3UrlKeyCodec;
    private final DiagnosesService diagnosesService;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(AiDiagnosesRequestedEvent event) {
        try {
            AiDiagnosesAccepted accepted = aiDiagnosesClient.requestDiagnoses(toRequest(event));
            if (accepted == null || accepted.products() == null) {
                log.error("AI 진단 접수 응답에 상품 정보가 없습니다. diagnosesId={}", event.diagnosesId());
                return;
            }
            diagnosesService.assignRuns(event.diagnosesId(), toRunIds(accepted));
        } catch (Exception e) {
            // TODO: AI 409·429·5xx·연결 실패 처리(#335 후속). 지금은 상품이 IN_PROGRESS로 남고 멈춘 진단 정리(#330)에 맡긴다.
            log.error("AI 진단 요청 실패. diagnosesId={}", event.diagnosesId(), e);
        }
    }

    // 상품의 텍스트·이미지·상세페이지 URL을 보낸다.
    private AiDiagnosesRequest toRequest(AiDiagnosesRequestedEvent event) {
        return new AiDiagnosesRequest(event.diagnosesId().toString(),
                event.products().stream().map(this::toProduct).toList());
    }

    private AiDiagnosesRequest.Product toProduct(AiDiagnosesRequestedEvent.ProductInput product) {
        List<String> textBlocks = StringUtils.hasText(product.sourceText()) ? List.of(product.sourceText()) : List.of();
        List<String> imageUrls = product.imageKeys().stream().map(s3UrlKeyCodec::toUrl).toList();
        return new AiDiagnosesRequest.Product(product.productId().toString(), textBlocks, imageUrls, product.sourceUrl());
    }

    private Map<UUID, String> toRunIds(AiDiagnosesAccepted accepted) {
        return accepted.products().stream()
                .collect(Collectors.toMap(
                        product -> UUID.fromString(product.productId()),
                        AiDiagnosesAccepted.AcceptedProduct::runId));
    }
}
