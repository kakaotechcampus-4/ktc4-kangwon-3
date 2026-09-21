package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final DiagnosesService diagnosesService;
    private final DiagnosesMapper diagnosesMapper;

    public DiagnosesCreateResponse createDiagnoses(UUID userId, DiagnosesCreateRequest request) {
        Diagnoses diagnoses = diagnosesService.createDiagnoses(diagnosesMapper.toCommand(userId, request));

        // TODO: AI 서버에 진단 요청(POST /api/diagnoses)을 보내고 processingStatus를 IN_PROGRESS로 전이?
        return diagnosesMapper.toCreateResponse(diagnoses);
    }

    public DiagnosesDetailResponse getDiagnoses(UUID userId, UUID diagnosesId) {
        Diagnoses diagnoses = diagnosesService.getDiagnoses(userId, diagnosesId);

        return diagnosesMapper.toDetailResponse(diagnoses);
    }

    public DiagnosesListResponse getDiagnosesList(UUID userId, ResultStatus resultStatus, Pageable pageable) {
        return diagnosesMapper.toListResponse(diagnosesService.getDiagnosesList(userId, resultStatus, pageable));
    }

    public void removeDiagnoses(UUID userId, UUID diagnosesId) {
        diagnosesService.removeDiagnoses(userId, diagnosesId);
    }
}
