package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface LawAmendmentRepository extends JpaRepository<LawAmendment, UUID> {
}
