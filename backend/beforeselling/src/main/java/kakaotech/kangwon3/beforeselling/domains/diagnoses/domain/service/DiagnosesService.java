package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesImageRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.IntStream;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DiagnosesService {

    private final DiagnosesRepository diagnosesRepository;
    private final DiagnosesImageRepository diagnosesImageRepository;

    // 진단서 + 이미지 저장
    @Transactional
    public Diagnoses createDiagnoses(DiagnosesCreateCommand command)  {
        Diagnoses diagnoses = diagnosesRepository.save(Diagnoses.pending(
                command.userId(),
                command.productName(),
                command.productImageUrl(),
                command.sourceType(),
                command.sourceUrl(),
                command.sourceText()
        ));

        createDiagnosesImages(diagnoses.getId(), command.imageUrls());
        log.debug("진단서 생성 완료. diagnosesId={}, userId={}", diagnoses.getId(), command.userId());


        return diagnoses;
    }

    // 단건 조회 + 소유권 검증
    @Transactional(readOnly = true)
    public Diagnoses getDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = diagnosesRepository.findById(diagnosesId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));

        if(!diagnoses.isOwnedBy(userId)) {
            throw new BaseException(CommonResponseCode.FORBIDDEN);
        }
        return diagnoses;
    }

    // 상세 응답용 이미지 목록
    @Transactional(readOnly = true)
    public List<DiagnosesImage> getDiagnosesImages(Long diagnosesId) {
        return diagnosesImageRepository.findByDiagnosesIdOrderBySortOrderAsc(diagnosesId);
    }

    // 목록 조회, 필터 유무 분기
    @Transactional(readOnly = true)
    public Page<Diagnoses> getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        if(resultStatus == null) {
            return diagnosesRepository.findByUserId(userId, pageable);
        }
        return diagnosesRepository.findByUserIdAndResultStatus(userId, resultStatus, pageable);
    }

    // 이미지 -> 진단서 순으로 삭제
    @Transactional
    public void removeDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = getDiagnoses(userId, diagnosesId);

        diagnosesImageRepository.deleteByDiagnosesId(diagnosesId);
        diagnosesRepository.delete(diagnoses);

        log.debug("진단서 삭제 완료. diagnosesId={}, userId={}", diagnosesId, userId);
    }

    // 업로드 순서를 sortOrder로 부여
    private void createDiagnosesImages(Long diagnosesId, List<String> imageUrls) {
        List<DiagnosesImage> images = IntStream.range(0, imageUrls.size())
                .mapToObj(index -> DiagnosesImage.of(diagnosesId, imageUrls.get(index), index))
                .toList();

        diagnosesImageRepository.saveAll(images);
    }

}
