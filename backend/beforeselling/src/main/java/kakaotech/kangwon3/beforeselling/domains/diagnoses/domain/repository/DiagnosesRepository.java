package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, Long> {

    // 소유권은 서비스에서 검증한다.
    @EntityGraph(attributePaths = "products")
    Optional<Diagnoses> findWithProductsById(Long diagnosesId);

    @EntityGraph(attributePaths = "products")
    List<Diagnoses> findWithProductsByUserId(Long userId);
}
