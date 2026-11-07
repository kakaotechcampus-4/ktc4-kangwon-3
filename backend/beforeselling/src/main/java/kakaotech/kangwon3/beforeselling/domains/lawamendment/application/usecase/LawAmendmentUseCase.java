package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper.LawAmendmentMapper;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class LawAmendmentUseCase {

    private final LawAmendmentService lawAmendmentService;
    private final UserService userService;
    private final LawAmendmentMapper lawAmendmentMapper;

    public LawAmendmentListResponse getLawAmendments(UUID userId) {
        if (!userService.getUser(userId).isLawAmendmentAlertEnabled()) {
            return new LawAmendmentListResponse(List.of());
        }
        return lawAmendmentMapper.toListResponse(lawAmendmentService.getRecheckProducts(userId));
    }
}
