package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3FileMover;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final DiagnosesService diagnosesService;
    private final DiagnosesMapper diagnosesMapper;
    private final S3FileMover s3FileMover;

    public DiagnosesCreateResponse createDiagnoses(Long userId, DiagnosesCreateRequest request) {
        DiagnosesCreateRequest movedRequest = moveKeysToPermanent(request);
        Diagnoses diagnoses = diagnosesService.createDiagnoses(diagnosesMapper.toCommand(userId, movedRequest));

        // TODO: AI 서버에 진단 요청(POST /api/diagnoses)을 보내고 processingStatus를 IN_PROGRESS로 전이?
        return diagnosesMapper.toCreateResponse(diagnoses);
    }

    // temp/ 경로에 업로드된 key를 정식 경로로 이동시킨 뒤, 이동된 key로 교체한 요청을 반환한다.
    private DiagnosesCreateRequest moveKeysToPermanent(DiagnosesCreateRequest request) {
        String movedProductImageKey = s3FileMover.moveToPermanent(request.productImageKey());
        List<String> movedImageKeys = s3FileMover.moveAllToPermanent(request.imageKeys());

        return new DiagnosesCreateRequest(
                request.productName(),
                movedProductImageKey,
                request.sourceType(),
                request.sourceUrl(),
                request.sourceText(),
                movedImageKeys
        );
    }

    public DiagnosesDetailResponse getDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = diagnosesService.getDiagnoses(userId, diagnosesId);

        return diagnosesMapper.toDetailResponse(diagnoses);
    }

    public DiagnosesListResponse getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        return diagnosesMapper.toListResponse(diagnosesService.getDiagnosesList(userId, resultStatus, pageable));
    }

    public void removeDiagnoses(Long userId, Long diagnosesId) {
        diagnosesService.removeDiagnoses(userId, diagnosesId);
    }
}
