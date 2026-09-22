package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, Long> {

    // 소유권을 조회 조건에 포함한다. 남의 진단서는 "없는 것"으로 취급해야
    // 404/403 차이로 id 존재 여부가 새어 나가지 않는다.
    @EntityGraph(attributePaths = "products")
    Optional<Diagnoses> findWithProductsByIdAndUserId(Long diagnosesId, Long userId);

    @EntityGraph(attributePaths = "products")
    List<Diagnoses> findWithProductsByUserId(Long userId);

    // 목록은 products를 fetch하지 않는다. @BatchSize로 묶어 읽으므로 N+1이 나지 않고,
    // 컬렉션 fetch join + 페이징 조합에서 생기는 메모리 페이징도 피할 수 있다.
    Page<Diagnoses> findByUserId(Long userId, Pageable pageable);

    // 결과 필터는 "해당 결과의 상품을 하나라도 가진 진단서"를 의미한다.
    @Query(value = """
            select distinct d from Diagnoses d
            join d.products p
            where d.userId = :userId and p.resultStatus = :resultStatus
            """,
            countQuery = """
            select count(distinct d) from Diagnoses d
            join d.products p
            where d.userId = :userId and p.resultStatus = :resultStatus
            """)
    Page<Diagnoses> findByUserIdAndProductResultStatus(@Param("userId") Long userId,
                                                       @Param("resultStatus") ResultStatus resultStatus,
                                                       Pageable pageable);
}