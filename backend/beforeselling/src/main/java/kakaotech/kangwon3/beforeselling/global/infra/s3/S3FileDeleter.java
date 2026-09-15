package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.Delete;
import software.amazon.awssdk.services.s3.model.DeleteObjectsRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectsResponse;
import software.amazon.awssdk.services.s3.model.ObjectIdentifier;

import java.util.List;

/**
 * 회원 탈퇴, 엔티티 삭제 등으로 DB에서 참조가 사라진 S3 오브젝트(고아 파일)를 key로 정리한다.
 * 정리 실패가 회원/엔티티 삭제 자체를 막지 않도록, 실패는 예외를 던지지 않고 로그만 남긴다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class S3FileDeleter {

    private static final int MAX_ATTEMPTS = 3;

    private final S3Client s3Client;
    private final S3Properties s3Properties;

    public void deleteAll(List<String> keys) {
        List<ObjectIdentifier> objectIdentifiers = keys.stream()
                .filter(StringUtils::hasText)
                .map(key -> ObjectIdentifier.builder().key(key).build())
                .toList();

        if (objectIdentifiers.isEmpty()) {
            return;
        }

        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            if (tryDelete(objectIdentifiers, attempt)) {
                return;
            }
        }
        log.error("S3 고아 파일 삭제가 {}회 재시도 후에도 실패했습니다. keys={}", MAX_ATTEMPTS, objectIdentifiers);
    }

    private boolean tryDelete(List<ObjectIdentifier> objectIdentifiers, int attempt) {
        try {
            DeleteObjectsResponse response = s3Client.deleteObjects(DeleteObjectsRequest.builder()
                    .bucket(s3Properties.bucket())
                    .delete(Delete.builder().objects(objectIdentifiers).build())
                    .build());

            if (!response.hasErrors()) {
                return true;
            }
            log.error("S3 고아 파일 일부 삭제 실패({}번째 시도). errors={}", attempt, response.errors());
        } catch (SdkException e) {
            log.error("S3 고아 파일 삭제 요청이 실패했습니다({}번째 시도). keys={}", attempt, objectIdentifiers, e);
        }
        return false;
    }
}
