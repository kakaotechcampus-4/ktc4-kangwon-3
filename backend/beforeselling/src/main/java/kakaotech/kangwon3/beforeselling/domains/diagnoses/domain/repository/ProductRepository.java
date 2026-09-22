package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ProductRepository extends JpaRepository<Product, UUID> {

    @EntityGraph(attributePaths = "images")
    Optional<Product> findWithImagesById(UUID productId);

    Page<Product> findByDiagnosesUserId(UUID userId, Pageable pageable);

    Page<Product> findByDiagnosesUserIdAndResultStatus(UUID userId, ResultStatus resultStatus, Pageable pageable);
}
