package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DiagnosesRepository extends JpaRepository<Diagnoses, Long> {

    List<Diagnoses> findByUserId(Long userId);
}
