package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DiagnosesImageRepository extends JpaRepository<DiagnosesImage, Long> {

    List<DiagnosesImage> findByDiagnosesIdBySortOrderAsc(Long diagnosesId);

    void deleteByDiagnosesId(Long diagnosesId);

}
