package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface LawAmendmentProductRepository extends JpaRepository<LawAmendmentProduct, UUID> {
}
