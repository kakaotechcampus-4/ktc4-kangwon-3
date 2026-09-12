package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, Long> {

    Page<Diagnoses> findByUserId(Long userId, Pageable pageable);

    Page<Diagnoses> findByUserIdAndResultStatus(Long userId, ResultStatus resultStatus, Pageable pageable);
}
