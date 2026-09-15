package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

    private final DiagnosesRepository diagnosesRepository;
    private final ApplicationEventPublisher eventPublisher;

    // 진단서 + 이미지 저장(이미지는 cascade로 함께 저장된다)
    @Transactional
    public Diagnoses createDiagnoses(DiagnosesCreateCommand command) {
        Diagnoses diagnoses = Diagnoses.pending(
                command.userId(),
                command.productName(),
                command.productImageKey(),
                command.sourceType(),
                command.sourceUrl(),
                command.sourceText()
        );
        diagnoses.addImages(command.imageKeys());

        Diagnoses saved = diagnosesRepository.save(diagnoses);
        log.debug("진단서 생성 완료. diagnosesId={}, userId={}", saved.getId(), command.userId());

        return saved;
    }

    // 단건 조회 + 소유권 검증
    public Diagnoses getDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = diagnosesRepository.findWithImagesById(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        if(!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.FORBIDDEN);
        }
        return diagnoses;
    }

    // 목록 조회, 필터 유무 분기
    public Page<Diagnoses> getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        if(resultStatus == null) {
            return diagnosesRepository.findByUserId(userId, pageable);
        }
        return diagnosesRepository.findByUserIdAndResultStatus(userId, resultStatus, pageable);
    }

    // 진단서 삭제(딸린 이미지는 cascade로 함께 삭제) 후 S3 삭제 이벤트 발행(AFTER_COMMIT 이후 비동기 처리)
    @Transactional
    public void removeDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = getDiagnoses(userId, diagnosesId);
        List<String> keys = collectImageKeys(List.of(diagnoses));

        diagnosesRepository.delete(diagnoses);
        eventPublisher.publishEvent(new S3FileDeleteEvent(keys));

        log.debug("진단서 삭제 완료. diagnosesId={}, userId={}", diagnosesId, userId);
    }

    // 회원 탈퇴 시 사용자의 진단서를 일괄 삭제하고 S3 삭제 이벤트를 한 번에 발행
    @Transactional
    public void removeAllByUserId(Long userId) {
        List<Diagnoses> diagnosesList = diagnosesRepository.findWithImagesByUserId(userId);
        if (diagnosesList.isEmpty()) {
            return;
        }

        List<String> keys = collectImageKeys(diagnosesList);

        diagnosesRepository.deleteAll(diagnosesList);
        eventPublisher.publishEvent(new S3FileDeleteEvent(keys));

        log.debug("회원 탈퇴에 따른 진단서 일괄 삭제 완료. userId={}, count={}", userId, diagnosesList.size());
    }

    private List<String> collectImageKeys(List<Diagnoses> diagnosesList) {
        List<String> keys = new ArrayList<>();
        for (Diagnoses diagnoses : diagnosesList) {
            if (diagnoses.getProductImageKey() != null) {
                keys.add(diagnoses.getProductImageKey());
            }
            for (DiagnosesImage image : diagnoses.getImages()) {
                keys.add(image.getImageKey());
            }
        }
        return keys;
    }
}
