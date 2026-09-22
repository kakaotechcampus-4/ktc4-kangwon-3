package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProductRepository extends JpaRepository<Product, UUID> {

    @EntityGraph(attributePaths = "images")
    Optional<Product> findWithImagesById(UUID productId);

    @EntityGraph(attributePaths = "images")
    List<Product> findWithImagesByUserId(UUID userId);

    Page<Product> findByUserId(UUID userId, Pageable pageable);

    Page<Product> findByUserIdAndResultStatus(UUID userId, ResultStatus resultStatus, Pageable pageable);
}
