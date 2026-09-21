package kakaotech.kangwon3.beforeselling.global.infra.s3.domain.repository;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3File;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3FileStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;

public interface S3FileRepository extends JpaRepository<S3File, Long> {

    List<S3File> findByKeyIn(List<String> keys);

    List<S3File> findByStatusAndCreatedAtBefore(S3FileStatus status, LocalDateTime threshold, Pageable pageable);

    void deleteByKeyIn(List<String> keys);
}
