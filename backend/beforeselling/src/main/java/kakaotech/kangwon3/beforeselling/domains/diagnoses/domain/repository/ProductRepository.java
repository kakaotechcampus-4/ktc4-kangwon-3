package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ProductRepository extends JpaRepository<Product, Long> {

    @EntityGraph(attributePaths = "images")
    Optional<Product> findWithImagesById(Long productId);

    Page<Product> findByDiagnosesUserId(Long userId, Pageable pageable);

    Page<Product> findByDiagnosesUserIdAndResultStatus(Long userId, ResultStatus resultStatus, Pageable pageable);
}
