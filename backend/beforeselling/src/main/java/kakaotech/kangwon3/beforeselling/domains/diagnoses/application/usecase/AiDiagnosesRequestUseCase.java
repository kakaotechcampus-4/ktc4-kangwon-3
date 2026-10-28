package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent.ProductInput;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesRequestException;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * AI에 진단을 요청하고, 접수(202)면 상품별 실행 식별자를 저장한다.
 * 실패는 AI가 요청을 받았는지에 따라 나눠 처리한다.
 * 진단서 생성 직후(AiDiagnosesRequestEventListener)와 대기 상품 재요청(PendingDiagnosesRetryScheduler)에서 사용한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiDiagnosesRequestUseCase {

    private final AiDiagnosesClient aiDiagnosesClient;
    private final S3UrlKeyCodec s3UrlKeyCodec;
    private final DiagnosesService diagnosesService;

    public void requestDiagnoses(AiDiagnosesRequestedEvent event) {
        UUID diagnosesId = event.diagnosesId();
        try {
            List<ProductInput> products = event.products();
            while (!products.isEmpty()) {
                products = request(diagnosesId, products);
            }
        } catch (Exception e) {
            log.error("AI 진단 요청 처리 실패. diagnosesId={}", diagnosesId, e);
        }
    }

    // 요청 후 다시 보낼 상품을 돌려준다. 끝났으면 빈 목록
    private List<ProductInput> request(UUID diagnosesId, List<ProductInput> products) {
        try {
            AiDiagnosesAccepted accepted = aiDiagnosesClient.requestDiagnoses(toRequest(diagnosesId, products));
            diagnosesService.assignRuns(diagnosesId, toRunIds(accepted));
            return List.of();
        } catch (AiDiagnosesRequestException e) {
            return handleFailure(diagnosesId, products, e);
        }
    }

    private List<ProductInput> handleFailure(UUID diagnosesId, List<ProductInput> products,
                                             AiDiagnosesRequestException e) {
        List<UUID> productIds = products.stream().map(ProductInput::productId).toList();
        return switch (e.getFailure()) {
            case CONFLICT -> excludeConflicts(diagnosesId, products, e.getConflictProductIds());
            case NOT_RECEIVED -> {
                log.warn("AI가 진단 요청을 받지 않아 재요청을 기다립니다. diagnosesId={}, status={}, productIds={}",
                        diagnosesId, e.getStatus(), productIds, e);
                diagnosesService.returnToPending(diagnosesId, productIds);
                yield List.of();
            }
            case UNKNOWN -> {
                // 다시 보내면 중복될 수 있어 진단 중으로 둔다. 스케줄러가 처리.
                log.warn("AI가 진단 요청을 접수했는지 알 수 없어 다시 보내지 않습니다. diagnosesId={}, productIds={}",
                        diagnosesId, productIds, e);
                yield List.of();
            }
            case REJECTED -> {
                log.error("AI가 진단 요청을 거절했습니다. diagnosesId={}, status={}, productIds={}",
                        diagnosesId, e.getStatus(), productIds, e);
                diagnosesService.failRejectedRequest(diagnosesId, productIds);
                yield List.of();
            }
        };
    }

    // AI는 진행 중인 상품이 하나라도 있으면 진단서 전체를 거절한다.
    // 충돌한 상품은 실행 식별자를 몰라 콜백을 받을 수 없으므로 실패 처리하고, 나머지만 다시 보낸다.
    private List<ProductInput> excludeConflicts(UUID diagnosesId, List<ProductInput> products,
                                                List<String> conflictProductIds) {
        List<UUID> conflicted = products.stream()
                .map(ProductInput::productId)
                .filter(productId -> conflictProductIds.contains(productId.toString()))
                .toList();

        if (conflicted.isEmpty()) {
            log.error("AI가 진단 요청을 409로 거절했지만 보낸 상품 중 충돌 상품이 없습니다. diagnosesId={}, conflictProductIds={}",
                    diagnosesId, conflictProductIds);
            return List.of();
        }

        log.warn("AI가 이전 진단을 진행 중인 상품을 실패 처리하고 나머지를 다시 요청합니다. diagnosesId={}, conflictProductIds={}",
                diagnosesId, conflicted);
        diagnosesService.failConflictedRequest(diagnosesId, conflicted);

        return products.stream()
                .filter(product -> !conflicted.contains(product.productId()))
                .toList();
    }

    // 상품의 텍스트·이미지·상세페이지 URL을 보낸다.
    private AiDiagnosesRequest toRequest(UUID diagnosesId, List<ProductInput> products) {
        return new AiDiagnosesRequest(diagnosesId.toString(), products.stream().map(this::toProduct).toList());
    }

    private AiDiagnosesRequest.Product toProduct(ProductInput product) {
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
