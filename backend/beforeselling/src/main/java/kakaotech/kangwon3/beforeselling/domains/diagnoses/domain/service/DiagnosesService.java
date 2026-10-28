package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

    // AI가 요청을 거절해 BE가 실패 처리할 때의 오류. 대부분 BE 코드·설정 문제라 다시 진단해도 같은 결과인 경우.
    static final String REQUEST_REJECTED_ERROR_CODE = "BE_AI_REQUEST_REJECTED";
    static final String REQUEST_REJECTED_ERROR_MESSAGE = "진단 요청이 거절되어 진단을 시작하지 못했습니다.";
    static final boolean REQUEST_REJECTED_ERROR_RETRYABLE = false;

    // 재요청 기한까지 AI가 요청을 받지 못했을 때의 오류. 일시적인 장애라 다시 진단하면 성공할 수 있음.
    static final String REQUEST_UNAVAILABLE_ERROR_CODE = "BE_AI_REQUEST_UNAVAILABLE";
    static final String REQUEST_UNAVAILABLE_ERROR_MESSAGE = "AI 서버가 요청을 받지 못해 진단을 시작하지 못했습니다.";
    static final boolean REQUEST_UNAVAILABLE_ERROR_RETRYABLE = true;

    private final DiagnosesRepository diagnosesRepository;
    private final S3FileService s3FileService;
    private final ApplicationEventPublisher eventPublisher;

    // 진단서 + 상품 + 상품 이미지 저장(하위는 cascade로 함께 저장된다)
    // 저장과 함께 진단을 시작하고, 커밋 후 AI에 진단을 요청하도록 이벤트를 발행한다.
    @Transactional
    public Diagnoses createDiagnoses(UUID userId, List<ProductCreateCommand> commands) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(commands.stream().map(this::toProduct).toList());
        // AI는 접수(202) 직후부터 콜백을 보내므로, 커밋 시점에 이미 진단 중이어야 결과를 받을 수 있다.
        diagnoses.startDiagnoses();

        s3FileService.markConfirmed(collectImageKeys(diagnoses));
        Diagnoses saved = diagnosesRepository.save(diagnoses);
        eventPublisher.publishEvent(toAiDiagnosesRequestedEvent(saved.getId(), saved.getProducts()));
        log.debug("진단서 생성 완료. diagnosesId={}, userId={}, 상품 수={}",
                saved.getId(), userId, commands.size());

        return saved;
    }

    /**
     * AI 접수 응답(202)의 상품별 실행 식별자를 저장한다.
     * 같은 진단서의 결과 콜백과 겹치지 않도록 진단서를 잠근 뒤 저장한다.
     */
    @Transactional
    public void assignRuns(UUID diagnosesId, Map<UUID, String> runIds) {
        Diagnoses diagnoses = diagnosesRepository.findByIdForUpdate(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        Map<UUID, Product> products = diagnoses.getProducts().stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));
        runIds.forEach((productId, runId) -> {
            Product product = products.get(productId);
            if (product == null) {
                log.warn("진단서에 없는 상품의 실행 식별자를 건너뜁니다. diagnosesId={}, productId={}",
                        diagnosesId, productId);
                return;
            }
            product.assignRun(runId);
        });
    }

    /**
     * AI가 요청을 받지 않은(429, 5xx, 연결 실패) 상품을 대기로 되돌린다. 재요청 스케줄러가 다시 보낸다.
     */
    @Transactional
    public void returnToPending(UUID diagnosesId, List<UUID> productIds) {
        Diagnoses diagnoses = diagnosesRepository.findByIdForUpdate(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        findProducts(diagnoses, productIds).forEach(product -> {
            // 실행 식별자가 있으면 AI가 실제로는 접수한 것
            if (product.getProcessingStatus() != ProcessingStatus.IN_PROGRESS || product.isRunAssigned()) {
                return;
            }
            product.returnToPending();
        });
        diagnoses.refreshProcessingStatus();
    }

    /**
     * AI가 다시 보내도 실패할 요청(400, 404, 405, 422, 501 등)으로 거절한 상품을 실패 처리한다.
     */
    @Transactional
    public void failRejectedRequest(UUID diagnosesId, List<UUID> productIds) {
        Diagnoses diagnoses = diagnosesRepository.findByIdForUpdate(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        findProducts(diagnoses, productIds).forEach(product -> {
            // 실행 식별자가 있으면 AI가 실제로는 접수한 것
            if (product.getProcessingStatus() != ProcessingStatus.IN_PROGRESS || product.isRunAssigned()) {
                return;
            }
            product.fail(null, REQUEST_REJECTED_ERROR_CODE, REQUEST_REJECTED_ERROR_MESSAGE,
                    REQUEST_REJECTED_ERROR_RETRYABLE);
        });
        diagnoses.refreshProcessingStatus();
    }

    /**
     * 대기 상품을 다시 AI에 보낼 수 있게 진단 중으로 바꾸고, 보낼 내용을 돌려준다.
     * 마지막 요청이 기한보다 오래된 상품은 더 기다리지 않고 실패 처리한다. 보낼 상품이 없으면 빈 값.
     */
    @Transactional
    public Optional<AiDiagnosesRequestedEvent> restartPendingProducts(UUID diagnosesId, LocalDateTime deadline) {
        Optional<Diagnoses> found = diagnosesRepository.findByIdForUpdate(diagnosesId);
        if (found.isEmpty()) {
            return Optional.empty();
        }

        Diagnoses diagnoses = found.get();
        List<Product> restarted = new ArrayList<>();
        for (Product product : diagnoses.getProducts()) {
            if (product.getProcessingStatus() != ProcessingStatus.PENDING) {
                continue;
            }
            // 생성 시각이 아니라 마지막 요청 시각 기준. 오래된 상품을 다시 진단할 때 재요청 없이 바로 실패하지 않도록 한다.
            if (product.isRequestedBefore(deadline)) {
                product.fail(null, REQUEST_UNAVAILABLE_ERROR_CODE, REQUEST_UNAVAILABLE_ERROR_MESSAGE,
                        REQUEST_UNAVAILABLE_ERROR_RETRYABLE);
                log.warn("AI 재요청 기한이 지나 실패 처리합니다. diagnosesId={}, productId={}, requestedAt={}",
                        diagnosesId, product.getId(), product.getRequestedAt());
                continue;
            }
            product.startDiagnoses();
            restarted.add(product);
        }
        diagnoses.refreshProcessingStatus();

        if (restarted.isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(toAiDiagnosesRequestedEvent(diagnosesId, restarted));
    }

    // 단건 조회 + 소유권 검증
    public Diagnoses getDiagnoses(UUID userId, UUID diagnosesId) {
        Diagnoses diagnoses = diagnosesRepository.findWithProductsById(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // 타인 소유 리소스도 404로 응답한다. 403을 주면 해당 id가 존재한다는 사실이
        // 노출되어 ID 탐색에 악용될 수 있다(CODE_CONVENTION.md 참고).
        if (!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.NOT_FOUND);
        }

        // open-in-view=false 라 DTO 매핑 시점에는 세션이 닫혀 있다.
        // products는 EntityGraph로 함께 조회되지만 그 하위 images와 진단 결과는 지연 상태이므로
        // 트랜잭션 안에서 강제로 초기화한다(@BatchSize 덕에 컬렉션별 추가 쿼리는 1번).
        diagnoses.getProducts().forEach(Product::loadDetail);

        return diagnoses;
    }

    // 회원 탈퇴 시 해당 사용자의 모든 진단서를 삭제한다.
    @Transactional
    public void removeAllByUserId(UUID userId) {
        List<Diagnoses> diagnosesList = diagnosesRepository.findWithProductsByUserId(userId);

        List<String> imageKeys = diagnosesList.stream()
                .flatMap(diagnoses -> collectImageKeys(diagnoses).stream())
                .toList();

        diagnosesRepository.deleteAll(diagnosesList);
        publishDeleteEvent(imageKeys);

        log.debug("회원 탈퇴에 따른 진단서 삭제 완료. userId={}, 진단서 수={}, 대상 key 수={}",
                userId, diagnosesList.size(), imageKeys.size());
    }

    private Product toProduct(ProductCreateCommand command) {
        Product product = Product.pending(
                command.productName(),
                command.productImageKey(),
                command.sourceType(),
                command.sourceUrl(),
                command.sourceText()
        );
        product.addImages(command.imageKeys());
        return product;
    }

    private List<String> collectImageKeys(Diagnoses diagnoses) {
        return diagnoses.getProducts().stream()
                .flatMap(product -> product.collectImageKeys().stream())
                .toList();
    }


    // 진단서에 없는 상품 ID는 건너뛴다.
    private List<Product> findProducts(Diagnoses diagnoses, List<UUID> productIds) {
        return diagnoses.getProducts().stream()
                .filter(product -> productIds.contains(product.getId()))
                .toList();
    }

    private AiDiagnosesRequestedEvent toAiDiagnosesRequestedEvent(UUID diagnosesId, List<Product> products) {
        return new AiDiagnosesRequestedEvent(diagnosesId, products.stream()
                .map(product -> new AiDiagnosesRequestedEvent.ProductInput(product.getId(), product.getSourceType(),
                        product.getSourceUrl(), product.getSourceText(), product.collectImageKeys()))
                .toList());
    }

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }
}