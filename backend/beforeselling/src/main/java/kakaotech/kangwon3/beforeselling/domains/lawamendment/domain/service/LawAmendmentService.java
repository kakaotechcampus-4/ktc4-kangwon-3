package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentProductRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class LawAmendmentService {

    private final LawAmendmentRepository lawAmendmentRepository;
    private final LawAmendmentProductRepository lawAmendmentProductRepository;
    private final ProductService productService;
    private final LawAmendmentMailService lawAmendmentMailService;

    /**
     * 법령 변경을 저장하고, 그 분야 검토에서 해당 법령을 인용한 상품을 재확인 대상으로 연결해 회원에게 메일로 알린다.
     * 메일은 받은 변경을 모두 반영한 뒤 회원당 한 통으로 묶어 보낸다.
     * 이미 받은 변경은 건너뛰고, 새로 저장한 변경만 돌려준다.
     */
    @Transactional
    public List<LawAmendment> createLawAmendments(List<LawAmendment> lawAmendments) {
        Map<LawAmendment, List<Product>> recheckProductsByAmendment = new LinkedHashMap<>();
        for (LawAmendment lawAmendment : lawAmendments) {
            if (isReceived(lawAmendment)) {
                log.debug("이미 받은 법령 변경을 건너뜁니다. documentId={}, serialNumber={}",
                        lawAmendment.getDocumentId(), lawAmendment.getSerialNumber());
                continue;
            }

            LawAmendment saved = lawAmendmentRepository.save(lawAmendment);
            recheckProductsByAmendment.put(saved, createRecheckProducts(saved));
        }

        if (!recheckProductsByAmendment.isEmpty()) {
            lawAmendmentMailService.sendLawAmendmentMails(recheckProductsByAmendment);
        }
        return List.copyOf(recheckProductsByAmendment.keySet());
    }

    private boolean isReceived(LawAmendment lawAmendment) {
        return lawAmendmentRepository.existsByDocumentIdAndSerialNumber(
                lawAmendment.getDocumentId(), lawAmendment.getSerialNumber());
    }

    private List<Product> createRecheckProducts(LawAmendment lawAmendment) {
        List<Product> products = productService.findCompletedByToolNameAndCitedLawName(
                lawAmendment.getToolName(), lawAmendment.getLawName());
        lawAmendmentProductRepository.saveAll(products.stream()
                .map(product -> LawAmendmentProduct.of(lawAmendment, product))
                .toList());

        log.info("법령 개정 재확인 대상 지정. lawAmendmentId={}, lawName={}, toolName={}, productCount={}",
                lawAmendment.getId(), lawAmendment.getLawName(), lawAmendment.getToolName(), products.size());
        return products;
    }

    /**
     * 사용자의 재확인 대상 상품을 법령 변경과 함께 조회한다.
     */
    public List<LawAmendmentProduct> getRecheckProducts(UUID userId) {
        return lawAmendmentProductRepository.findWithLawAmendmentAndProductByUserId(userId);
    }

    /**
     * 상품을 모든 법령 변경의 재확인 대상에서 뺀다.
     */
    @Transactional
    public void removeRecheckProducts(UUID productId) {
        int removed = lawAmendmentProductRepository.deleteByProductId(productId);
        log.debug("재확인 대상 해제. productId={}, removedCount={}", productId, removed);
    }
}
