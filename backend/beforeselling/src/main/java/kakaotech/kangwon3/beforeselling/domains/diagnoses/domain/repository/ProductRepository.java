package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProductRepository extends JpaRepository<Product, UUID> {

    @Query("""
            select p from Product p
            where p.diagnoses.userId = :userId
              and (:resultStatus is null or p.resultStatus = :resultStatus)
              and (cast(:keyword as String) is null or lower(p.productName) like lower(concat('%', cast(:keyword as String), '%')))
            """)
    Page<Product> search(@Param("userId") UUID userId,
                         @Param("resultStatus") ResultStatus resultStatus,
                         @Param("keyword") String keyword,
                         Pageable pageable);

    @Query("select p.diagnoses.id from Product p where p.id = :productId")
    Optional<UUID> findDiagnosesIdById(@Param("productId") UUID productId);

    @EntityGraph(attributePaths = "images")
    @Query("select p from Product p where p.id = :productId and p.diagnoses.userId = :userId")
    Optional<Product> findWithImagesByIdAndUserId(@Param("productId") UUID productId,
                                                  @Param("userId") UUID userId);

    // 멈춘 진단 정리용. 상태 변화가 오래된 순으로 ID만 가져온다.
    @Query("""
        select p.id from Product p
        where p.processingStatus = :status
          and p.updatedAt < :threshold
        order by p.updatedAt asc
        """)
    List<UUID> findIdsByStatusUpdatedBefore(@Param("status") ProcessingStatus status,
                                            @Param("threshold") LocalDateTime threshold,
                                            Pageable pageable);
}
