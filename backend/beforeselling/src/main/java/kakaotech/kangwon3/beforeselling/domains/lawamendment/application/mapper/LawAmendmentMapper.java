package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class LawAmendmentMapper {

    public List<LawAmendment> toLawAmendments(LawChangeCallbackRequest request) {
        return request.changes().stream()
                .map(this::toLawAmendment)
                .toList();
    }

    private LawAmendment toLawAmendment(PublicLawChangeDto change) {
        return LawAmendment.builder()
                .lawName(change.lawName())
                .documentId(change.documentId())
                .admrul(change.admrul())
                .toolName(change.toolName())
                .serialNumber(change.serialNumber())
                .previousSerialNumber(change.previousSerialNumber())
                .revisionType(change.revisionType())
                .enforceDate(change.enforceDate())
                .issuedDate(change.issuedDate())
                .build();
    }
}
