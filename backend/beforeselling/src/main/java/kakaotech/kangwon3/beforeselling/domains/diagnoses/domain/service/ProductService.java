package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

    // BE가 직접 실패 처리할 때의 오류 코드
    static final String STUCK_ERROR_CODE = "BE_DIAGNOSES_TIMEOUT";
    static final String STUCK_ERROR_MESSAGE = "진단 결과를 받지 못해 진단을 종료했습니다.";
    // AI_TIMEOUT과 같은 일시적인 실패라 다시 진단하면 성공할 수 있다.
    static final boolean STUCK_ERROR_RETRYABLE = true;

    private final ProductRepository productRepository;
    private final DiagnosesRepository diagnosesRepository;
    private final ApplicationEventPublisher eventPublisher;

    /**
     * 마이페이지 상품 목록. 진단서가 아니라 상품 단위로 조회한다.
     */
    public Page<Product> getProductList(UUID userId, ResultStatus resultStatus,
                                        String keyword, Pageable pageable) {
        return productRepository.search(userId, resultStatus, normalizeKeyword(keyword), pageable);
    }

    /**
     * 상품 단건 조회. 마이페이지에서 상품 하나의 진단 결과를 볼 때 쓴다.
     */
    public Product getProduct(UUID userId, UUID productId) {
        // 없는 상품과 남의 상품 모두 빈 결과라 같은 NOT_FOUND 로 응답한다.
        Product product = productRepository.findWithImagesByIdAndUserId(productId, userId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        product.loadDetail();

        return product;
    }

    /**
     * 상품 단건 삭제. 딸린 이미지는 cascade로 함께 삭제되고,
     * 진단서에 남은 상품이 없으면 진단서도 정리한다
     */
    @Transactional
    public void removeProduct(UUID userId, UUID productId) {
        UUID diagnosesId = productRepository.findDiagnosesIdById(productId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // 소유권은 락 쿼리에서 함께 검증한다. 이유는 DiagnosesRepository의 findByIdAndUserIdForUpdate 참고
        // 없는 진단서와 남의 진단서 모두 빈 결과라 같은 NOT_FOUND 로 응답한다.
        Diagnoses diagnoses = diagnosesRepository.findByIdAndUserIdForUpdate(diagnosesId, userId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));


        Product product = diagnoses.getProducts().stream()
                .filter(candidate -> candidate.getId().equals(productId))
                .findFirst()
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        List<String> imageKeys = product.collectImageKeys();

        diagnoses.removeProduct(product);

        boolean diagnosesRemoved = diagnoses.isEmpty();
        if (diagnosesRemoved) {
            diagnosesRepository.delete(diagnoses);
        }

        publishDeleteEvent(imageKeys);

        log.debug("상품 삭제 완료. productId={}, userId={}, 진단서 함께 삭제={}",
                productId, userId, diagnosesRemoved);
    }

    /**
     * AI 진단 결과 반영(결과 콜백). 상품을 완료 처리하고 진단서 전체 상태를 다시 계산한다.
     * 이미 반영된 결과(재전송)는 무시한다.
     */
    @Transactional
    public void completeDiagnoses(UUID diagnosesId, UUID productId, String runId, AssessmentContent content) {
        // 같은 진단서의 다른 상품 콜백과 동시에 진단서 상태를 재계산하지 않도록 진단서를 잠근다.
        Diagnoses diagnoses = diagnosesRepository.findByIdForUpdate(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // 진단서와 상품 짝이 맞지 않는 경우도 같은 NOT_FOUND로 응답한다.
        Product product = diagnoses.getProducts().stream()
                .filter(candidate -> candidate.getId().equals(productId))
                .findFirst()
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // 현재 runId와 다르면 202 응답의 runId를 저장하기 전에 도착한 새 실행의 콜백일 수 있어 다시 보내 달라고 한다.
        // AI는 COMMON-009(409)일 때만 다시 보내고, 정말 이전 실행의 콜백이면 재시도 끝에 버려진다.
        if (!product.isCurrentRun(runId)) {
            log.debug("현재 실행이 아닌 결과 콜백.. productId={}, runId={}, currentRunId={}",
                    productId, runId, product.getRunId());
            throw new BaseException(CommonResponseCode.LOCK_CONFLICT);
        }
        if (product.hasResult()) {
            log.debug("이미 결과가 반영된 상품의 결과 콜백을 무시합니다. productId={}, runId={}", productId, runId);
            return;
        }

        product.complete(content);
        diagnoses.refreshProcessingStatus();

        log.debug("상품 진단 결과 반영 완료. diagnosesId={}, productId={}, resultStatus={}",
                diagnosesId, productId, content.resultStatus());
    }

    @Transactional
    public boolean failStuckDiagnoses(UUID productId, LocalDateTime threshold) {
        Optional<UUID> diagnosesId = productRepository.findDiagnosesIdById(productId);
        if (diagnosesId.isEmpty()) {
            return false;
        }

        Optional<Product> found = diagnosesRepository.findByIdForUpdate(diagnosesId.get())
                .flatMap(diagnoses -> diagnoses.getProducts().stream()
                        .filter(candidate -> candidate.getId().equals(productId))
                        .findFirst());
        if (found.isEmpty()) {
            return false;
        }

        Product product = found.get();
        if (product.getProcessingStatus() != ProcessingStatus.IN_PROGRESS
                || !product.getUpdatedAt().isBefore(threshold)) {
            return false;
        }

        LocalDateTime lastUpdatedAt = product.getUpdatedAt();
        product.fail(null, STUCK_ERROR_CODE, STUCK_ERROR_MESSAGE, STUCK_ERROR_RETRYABLE);
        product.getDiagnoses().refreshProcessingStatus();

        log.warn("멈춘 진단 실패 처리. productId={}, diagnosesId={}, runId={}, lastUpdatedAt={}",
                productId, diagnosesId.get(), product.getRunId(), lastUpdatedAt);
        return true;
    }

    /**
     * 멈춘 진단 정리용. 진행 중이면서 마지막 상태 변경이 기준 시각보다 오래된 상품 ID를 오래된 순으로 가져온다.
     */
    public List<UUID> findStuckProductIds(LocalDateTime threshold, int limit) {
        return productRepository.findIdsByStatusUpdatedBefore(
                ProcessingStatus.IN_PROGRESS, threshold, PageRequest.of(0, limit));
    }

    // 빈 문자열로 들어온 검색어는 "검색하지 않음"으로 취급한다.
    private String normalizeKeyword(String keyword) {
        return StringUtils.hasText(keyword) ? keyword.trim() : null;
    }

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }

}
