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

@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final DiagnosesService diagnosesService;
    private final DiagnosesMapper diagnosesMapper;

    public DiagnosesCreateResponse createDiagnoses(Long userId, DiagnosesCreateRequest request) {
        Diagnoses diagnoses = diagnosesService.createDiagnoses(userId, diagnosesMapper.toCommands(request));

        // TODO: AI 서버에 진단 요청을 보내고 상품들의 processingStatus를 IN_PROGRESS로 전이
        return diagnosesMapper.toCreateResponse(diagnoses);
    }

    public DiagnosesDetailResponse getDiagnoses(Long userId, Long diagnosesId) {
        return diagnosesMapper.toDetailResponse(diagnosesService.getDiagnoses(userId, diagnosesId));
    }

    public DiagnosesListResponse getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        return diagnosesMapper.toListResponse(diagnosesService.getDiagnosesList(userId, resultStatus, pageable));
    }

    public void removeDiagnoses(Long userId, Long diagnosesId) {
        diagnosesService.removeDiagnoses(userId, diagnosesId);
    }
}