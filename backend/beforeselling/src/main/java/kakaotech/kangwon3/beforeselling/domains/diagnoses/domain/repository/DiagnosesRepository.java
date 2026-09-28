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

    // @EntityGraph 를 붙이지 않는다. 붙이면 Hibernate 가 조인 조회(락 없음)와 잠금 쿼리를
    // 나눠 실행해서, 상품 목록을 잠그기 전에 읽게 된다.
    // 그러면 동시 삭제 시 서로의 삭제를 못 보고 빈 진단서가 남는다.
    // 상품 목록은 락을 얻은 뒤 지연 로딩으로 읽어야 한다.
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select d from Diagnoses d where d.id = :diagnosesId")
    Optional<Diagnoses> findByIdForUpdate(@Param("diagnosesId") UUID diagnosesId);
}
