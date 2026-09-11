package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final DiagnosesService diagnosesService;
    private final DiagnosesMapper diagnosesMapper;

    public void createDiagnoses(Long userId, DiagnosesCreateRequest request) {
        diagnosesService.createDiagnoses(diagnosesMapper.toCommand(userId, request));

        // TODO: AI 서버에 진단 요청(POST /api/diagnoses)을 보내고 processingStatus를 IN_PROGRESS로 전이?
    }

    public DiagnosesDetailResponse getDiagnoses(Long userId, Long diagnosesId) {
        Diagnoses diagnoses = diagnosesService.getDiagnoses(userId, diagnosesId);
        List<DiagnosesImage> images = diagnosesService.getDiagnosesImages(diagnosesId);

        return diagnosesMapper.toDetailResponse(diagnoses, images);
    }

    public DiagnosesListResponse getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        return diagnosesMapper.toListResponse(diagnosesService.getDiagnosesList(userId, resultStatus, pageable));
    }

    public void removeDiagnoses(Long userId, Long diagnosesId) {
        diagnosesService.removeDiagnoses(userId, diagnosesId);
    }
}
