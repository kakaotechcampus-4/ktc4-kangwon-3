package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
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

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

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
        diagnoses.startDiagnosis();

        s3FileService.markConfirmed(collectImageKeys(diagnoses));
        Diagnoses saved = diagnosesRepository.save(diagnoses);
        eventPublisher.publishEvent(toAiDiagnosesRequestedEvent(saved));
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
        // products는 EntityGraph로 함께 조회되지만 그 하위 images는 지연 상태이므로
        // 트랜잭션 안에서 강제로 초기화한다(@BatchSize 덕에 추가 쿼리는 1번).
        diagnoses.getProducts().forEach(product -> product.getImages().size());

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


    private AiDiagnosesRequestedEvent toAiDiagnosesRequestedEvent(Diagnoses diagnoses) {
        return new AiDiagnosesRequestedEvent(diagnoses.getId(), diagnoses.getProducts().stream()
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