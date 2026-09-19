package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

    private final DiagnosesRepository diagnosesRepository;

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

    // 진단서 삭제(딸린 이미지는 cascade로 함께 삭제)
    @Transactional
    public void removeDiagnoses(Long userId, Long diagnosesId) {
        diagnosesRepository.delete(getDiagnoses(userId, diagnosesId));

        log.debug("진단서 삭제 완료. diagnosesId={}, userId={}", diagnosesId, userId);
    }
}
