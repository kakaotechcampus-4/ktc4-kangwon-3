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
    //
    // 다른 조회와 달리 소유권을 쿼리 조건으로 거른다.
    // 서비스에서 isOwnedBy 로 검증하면 확인 전에 남의 진단서 행이 이미 잠겨,
    // 남의 productId 만으로 그 사용자의 삭제 요청을 막을 수 있다.
    // FOR UPDATE 는 WHERE 를 통과한 행만 잠그므로, 남의 진단서는 잠기지 않고 빈 결과가 된다.
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select d from Diagnoses d where d.id = :diagnosesId and d.userId = :userId")
    Optional<Diagnoses> findByIdAndUserIdForUpdate(@Param("diagnosesId") UUID diagnosesId,
                                                   @Param("userId") UUID userId);
}
