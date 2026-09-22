package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3File;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * presigned URL 발급 후 24시간이 지나도 진단서 생성으로 이어지지 않은 고아 파일을 정리한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class S3OrphanFileCleanupScheduler {

    private static final int BATCH_SIZE = 1000;
    private static final long ORPHAN_THRESHOLD_HOURS = 24;

    private final S3FileService s3FileService;
    private final S3ObjectDeleter s3ObjectDeleter;

    @Scheduled(cron = "0 0 * * * *")
    public void cleanupOrphanFiles() {
        LocalDateTime threshold = LocalDateTime.now().minusHours(ORPHAN_THRESHOLD_HOURS);
        Pageable pageable = PageRequest.of(0, BATCH_SIZE);

        List<S3File> expired;
        while (!(expired = s3FileService.findExpiredPending(threshold, pageable)).isEmpty()) {
            List<String> keys = expired.stream().map(S3File::getKey).toList();
            try {
                s3ObjectDeleter.deleteAll(keys);
                s3FileService.removeByKeys(keys);
            } catch (Exception e) {
                log.error("고아 파일 정리 실패. keys={}", keys, e);
                return;
            }
        }
    }
}
