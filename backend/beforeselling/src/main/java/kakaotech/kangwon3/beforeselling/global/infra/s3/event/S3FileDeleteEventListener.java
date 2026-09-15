package kakaotech.kangwon3.beforeselling.global.infra.s3.event;

import kakaotech.kangwon3.beforeselling.global.infra.s3.S3FileDeleter;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * DB 트랜잭션이 커밋된 이후에만(AFTER_COMMIT) 비동기로 S3 삭제를 수행한다.
 * 트랜잭션이 롤백되면 이벤트 자체가 발행되지 않으므로 파일이 잘못 지워지지 않는다.
 */
@Component
@RequiredArgsConstructor
public class S3FileDeleteEventListener {

    private final S3FileDeleter s3FileDeleter;

    @Async("s3TaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(S3FileDeleteEvent event) {
        s3FileDeleter.deleteAll(event.keys());
    }
}
