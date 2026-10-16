package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
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
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

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
        return productRepository.findWithImagesByIdAndUserId(productId, userId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));
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
    public void completeDiagnosis(UUID diagnosesId, UUID productId, String runId, AssessmentContent content) {
        // 같은 진단서의 다른 상품 콜백과 동시에 진단서 상태를 재계산하지 않도록 진단서를 잠근다.
        Diagnoses diagnoses = diagnosesRepository.findByIdForUpdate(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // 진단서와 상품 짝이 맞지 않는 경우도 같은 NOT_FOUND로 응답한다.
        Product product = diagnoses.getProducts().stream()
                .filter(candidate -> candidate.getId().equals(productId))
                .findFirst()
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        // TODO: 진단 요청의 202 응답에서 runId를 저장(assignRun)하는 흐름이 구현되면 주석을 푼다.
        //  지금은 runId가 항상 null이라, 켜 두면 모든 결과가 409(재시도) 또는 이전 실행으로 무시된다.
        //  재실행(resume) 시 이전 runId를 비우지 않으면 새 실행의 결과가 이전 실행으로 무시되므로 함께 확인한다.
        // // 202 응답의 runId를 저장하기 전에 도착한 콜백. AI는 COMMON-009(409)일 때만 다시 보낸다.
        // if (!product.isRunAssigned()) {
        //     throw new BaseException(CommonResponseCode.LOCK_CONFLICT);
        // }
        // if (!product.isCurrentRun(runId)) {
        //     log.info("이전 실행의 결과 콜백을 무시합니다. productId={}, runId={}, currentRunId={}",
        //             productId, runId, product.getRunId());
        //     return;
        // }
        if (product.hasResult()) {
            log.info("이미 결과가 반영된 상품의 결과 콜백을 무시합니다. productId={}, runId={}", productId, runId);
            return;
        }

        product.complete(content);
        diagnoses.refreshProcessingStatus();

        log.debug("상품 진단 결과 반영 완료. diagnosesId={}, productId={}, resultStatus={}",
                diagnosesId, productId, content.resultStatus());
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
