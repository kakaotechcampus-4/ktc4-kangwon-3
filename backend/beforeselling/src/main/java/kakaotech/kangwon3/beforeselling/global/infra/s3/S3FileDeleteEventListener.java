package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * 엔티티 삭제/회원 탈퇴 등으로 더 이상 필요 없어진 S3 객체를, 해당 DB 트랜잭션이 커밋된 뒤 비동기로 삭제한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class S3FileDeleteEventListener {

    private final S3ObjectDeleter s3ObjectDeleter;
    private final S3FileService s3FileService;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(S3FileDeleteRequestedEvent event) {
        try {
            s3ObjectDeleter.deleteAll(event.keys());
            s3FileService.removeByKeys(event.keys());
        } catch (Exception e) {
            log.error("S3 파일 삭제 실패. keys={}", event.keys(), e);
        }
    }
}
