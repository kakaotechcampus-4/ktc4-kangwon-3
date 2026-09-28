package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import jakarta.persistence.LockModeType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, UUID> {

    // 소유권은 서비스에서 검증한다.
    @EntityGraph(attributePaths = "products")
    Optional<Diagnoses> findWithProductsById(UUID diagnosesId);

    @EntityGraph(attributePaths = "products")
    List<Diagnoses> findWithProductsByUserId(UUID userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select d from Diagnoses d where d.id = :diagnosesId")
    Optional<Diagnoses> findByIdForUpdate(@Param("diagnosesId") UUID diagnosesId);
}
