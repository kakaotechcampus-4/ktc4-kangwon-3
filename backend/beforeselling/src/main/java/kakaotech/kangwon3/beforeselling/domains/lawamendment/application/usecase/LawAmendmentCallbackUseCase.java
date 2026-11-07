package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper.LawAmendmentMapper;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class LawAmendmentCallbackUseCase {

    private final LawAmendmentService lawAmendmentService;
    private final LawAmendmentMapper lawAmendmentMapper;

    public void receiveLawChanges(LawChangeCallbackRequest request) {
        List<LawAmendment> created = lawAmendmentService.createLawAmendments(
                lawAmendmentMapper.toLawAmendments(request));

        log.info("AI 법령 변경 콜백 수신. receivedCount={}, createdCount={}",
                request.changes().size(), created.size());
    }
}
