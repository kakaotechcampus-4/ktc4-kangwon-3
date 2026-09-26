package kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3File;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3FileStatus;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.repository.S3FileRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class S3FileService {

    private final S3FileRepository s3FileRepository;

    @Transactional
    public void markPending(String key) {
        s3FileRepository.save(S3File.pending(key));
    }

    @Transactional
    public void markConfirmed(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        s3FileRepository.findByKeyIn(keys).forEach(S3File::confirm);
    }

    @Transactional
    public void removeByKeys(List<String> keys) {
        if (CollectionUtils.isEmpty(keys)) {
            return;
        }
        s3FileRepository.deleteByKeyIn(keys);
    }

    public List<S3File> findExpiredPending(LocalDateTime threshold, Pageable pageable) {
        return s3FileRepository.findByStatusAndCreatedAtBefore(S3FileStatus.PENDING, threshold, pageable);
    }
}
