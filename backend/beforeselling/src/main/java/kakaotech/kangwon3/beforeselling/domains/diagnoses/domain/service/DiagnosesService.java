package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

    private final DiagnosesRepository diagnosesRepository;
    private final S3FileService s3FileService;
    private final ApplicationEventPublisher eventPublisher;

    // 진단서 + 상품 + 상품 이미지 저장(하위는 cascade로 함께 저장된다)
    @Transactional
    public Diagnoses createDiagnoses(Long userId, List<ProductCreateCommand> commands) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(commands.stream().map(this::toProduct).toList());

        s3FileService.markConfirmed(collectImageKeys(diagnoses));
        Diagnoses saved = diagnosesRepository.save(diagnoses);
        log.debug("진단서 생성 완료. diagnosesId={}, userId={}, 상품 수={}",
                saved.getId(), userId, commands.size());

        return saved;
    }

    // 단건 조회 + 소유권 검증
    public Diagnoses getDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = diagnosesRepository.findWithProductsById(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        if (!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.FORBIDDEN);
        }

        // open-in-view=false 라 DTO 매핑 시점에는 세션이 닫혀 있다.
        // products는 EntityGraph로 함께 조회되지만 그 하위 images는 지연 상태이므로
        // 트랜잭션 안에서 강제로 초기화한다(@BatchSize 덕에 추가 쿼리는 1번).
        diagnoses.getProducts().forEach(product -> product.getImages().size());

        return diagnoses;
    }

    // 목록 조회, 결과 필터 유무 분기
    public Page<Diagnoses> getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        Page<Diagnoses> page = (resultStatus == null)
                ? diagnosesRepository.findByUserId(userId, pageable)
                : diagnosesRepository.findByUserIdAndProductResultStatus(userId, resultStatus, pageable);

        page.getContent().forEach(diagnoses -> diagnoses.getProducts().size());

        return page;
    }

    // 진단서 삭제(상품과 이미지는 cascade로 함께 삭제)
    @Transactional
    public void removeDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = getDiagnoses(userId, diagnosesId);
        List<String> imageKeys = collectImageKeys(diagnoses);

        diagnosesRepository.delete(diagnoses);
        publishDeleteEvent(imageKeys);

        log.debug("진단서 삭제 완료. diagnosesId={}, userId={}", diagnosesId, userId);
    }

    // 회원 탈퇴 시 해당 사용자의 모든 진단서를 삭제한다.
    @Transactional
    public void removeAllByUserId(Long userId) {
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
                .flatMap(product -> collectImageKeys(product).stream())
                .toList();
    }

    private List<String> collectImageKeys(Product product) {
        List<String> keys = new ArrayList<>();
        if (product.getProductImageKey() != null) {
            keys.add(product.getProductImageKey());
        }
        product.getImages().stream().map(ProductImage::getImageKey).forEach(keys::add);
        return keys;
    }

    private void publishDeleteEvent(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        eventPublisher.publishEvent(new S3FileDeleteRequestedEvent(keys));
    }
}