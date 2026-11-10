package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final DiagnosesService diagnosesService;
    private final UserService userService;
    private final DiagnosesMapper diagnosesMapper;

    public DiagnosesCreateResponse createDiagnoses(UUID userId, DiagnosesCreateRequest request) {
        // 탈퇴 후 남은 액세스 토큰으로 진단서가 생성되지 않도록 막는다.
        userService.validateExists(userId);
        Diagnoses diagnoses = diagnosesService.createDiagnoses(userId, diagnosesMapper.toCommands(request));
        return diagnosesMapper.toCreateResponse(diagnoses);
    }

    public DiagnosesDetailResponse getDiagnoses(UUID userId, UUID diagnosesId) {
        return diagnosesMapper.toDetailResponse(diagnosesService.getDiagnoses(userId, diagnosesId));
    }
}
