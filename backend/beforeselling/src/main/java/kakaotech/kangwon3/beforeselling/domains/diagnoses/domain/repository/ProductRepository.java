package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface ProductRepository extends JpaRepository<Product, UUID> {

    @EntityGraph(attributePaths = "images")
    Optional<Product> findWithImagesById(UUID productId);

    @Query("""
            select p from Product p
            where p.diagnoses.userId = :userId
              and (:resultStatus is null or p.resultStatus = :resultStatus)
              and (:keyword is null or lower(p.productName) like lower(concat('%', :keyword, '%')))
            """)
    Page<Product> search(@Param("userId") UUID userId,
                         @Param("resultStatus") ResultStatus resultStatus,
                         @Param("keyword") String keyword,
                         Pageable pageable);
}
