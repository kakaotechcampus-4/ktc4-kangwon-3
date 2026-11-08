package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentResponse.RecheckProductResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

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

    // 재확인 대상 상품을 법령 변경별로 묶는다. 조회 순서를 그대로 지킨다.
    public LawAmendmentListResponse toListResponse(List<LawAmendmentProduct> recheckProducts) {
        Map<LawAmendment, List<RecheckProductResponse>> grouped = recheckProducts.stream()
                .collect(Collectors.groupingBy(
                        LawAmendmentProduct::getLawAmendment,
                        LinkedHashMap::new,
                        Collectors.mapping(recheckProduct -> new RecheckProductResponse(
                                        recheckProduct.getProduct().getId(),
                                        recheckProduct.getProduct().getDiagnoses().getId(),
                                        recheckProduct.getProduct().getProductName()),
                                Collectors.toList())));

        return new LawAmendmentListResponse(grouped.entrySet().stream()
                .map(entry -> toResponse(entry.getKey(), entry.getValue()))
                .toList());
    }

    private LawAmendmentResponse toResponse(LawAmendment lawAmendment, List<RecheckProductResponse> products) {
        return new LawAmendmentResponse(
                lawAmendment.getId(),
                lawAmendment.getLawName(),
                lawAmendment.getRevisionType(),
                lawAmendment.getToolName(),
                lawAmendment.getEnforceDate(),
                products);
    }
}
