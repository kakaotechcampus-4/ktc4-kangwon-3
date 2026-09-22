package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, UUID> {

    @EntityGraph(attributePaths = "images")
    Optional<Diagnoses> findWithImagesById(UUID diagnosesId);

    @EntityGraph(attributePaths = "images")
    List<Diagnoses> findWithImagesByUserId(UUID userId);

    Page<Diagnoses> findByUserId(UUID userId, Pageable pageable);

    Page<Diagnoses> findByUserIdAndResultStatus(UUID userId, ResultStatus resultStatus, Pageable pageable);
}
