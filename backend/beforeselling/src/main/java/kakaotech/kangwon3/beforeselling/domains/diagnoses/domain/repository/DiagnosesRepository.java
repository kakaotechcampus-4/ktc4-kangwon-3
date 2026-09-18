package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, Long> {
    
    @EntityGraph(attributePaths = "images")
    Optional<Diagnoses> findWithImagesById(Long diagnosesId);

    @EntityGraph(attributePaths = "images")
    List<Diagnoses> findWithImagesByUserId(Long userId);

    Page<Diagnoses> findByUserId(Long userId, Pageable pageable);

    Page<Diagnoses> findByUserIdAndResultStatus(Long userId, ResultStatus resultStatus, Pageable pageable);
}
